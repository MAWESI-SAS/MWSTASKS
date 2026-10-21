# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Relaciones en lote, por id externo (migración y copia incremental desde ClickUp): "relacionada con" y dependencias.

La API v1 de Plane crea relaciones de a un work item por pedido y dispara un aviso por cada una. Acá:
- un pedido trae hasta MAX_PAIRS pares de ids externos, de cualquier proyecto del workspace;
- "relation_type": "relates_to" (por defecto, el orden del par no importa) o "blocked_by" ([a, b] = a espera a b, como
  task_id / depends_on de ClickUp);
- solo crea lo que falta: si ya hay una relación entre las 2 tareas (de cualquier tipo, en cualquier sentido,
  o borrada a mano en MWSTASKS) no se toca. Única excepción: una dependencia pisa un "relacionada con" vivo entre las
  mismas tareas (ClickUp las tiene como dependencia; el "relacionada" vino de sus tareas vinculadas);
- no borra nada.
"""
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView as PlaneKeyAPIView
from plane.app.permissions import ROLE
from plane.db.models import Issue, IssueRelation, WorkspaceMember

MAX_PAIRS = 1000
RELATES_TO = "relates_to"
BLOCKED_BY = "blocked_by"
FORBIDDEN = Response({"error": "No tienes permiso para esto."}, status=status.HTTP_403_FORBIDDEN)


def _pairs(raw, directed=False):
    """[[a, b], ...] -> set de pares (ordenados si no tienen sentido; sin repetidos ni una tarea consigo misma).
    None si el formato no sirve."""
    if not isinstance(raw, list) or len(raw) > MAX_PAIRS:
        return None
    out = set()
    for p in raw:
        if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(isinstance(x, str) and x for x in p):
            return None
        a, b = p
        if a != b:
            out.add((a, b) if directed else (min(a, b), max(a, b)))
    return out


class RelationsBatchKeyEndpoint(PlaneKeyAPIView):
    """POST {"external_source": "clickup", "relation_type"?: "relates_to"|"blocked_by", "pairs": [[ext_a, ext_b], ...]}
    -> {"creadas", "ya_estaban", "sin_tarea"} (+ "convertidas" con blocked_by). Solo admins del workspace: las relaciones cruzan proyectos."""

    def post(self, request, slug):
        if not WorkspaceMember.objects.filter(
            member=request.user, workspace__slug=slug, role=ROLE.ADMIN.value, is_active=True
        ).exists():
            return FORBIDDEN
        source = request.data.get("external_source")
        rtype = request.data.get("relation_type") or RELATES_TO
        if rtype not in (RELATES_TO, BLOCKED_BY):
            return Response({"error": "relation_type: relates_to o blocked_by."}, status=status.HTTP_400_BAD_REQUEST)
        pairs = _pairs(request.data.get("pairs"), directed=rtype == BLOCKED_BY)
        if not isinstance(source, str) or not source or pairs is None:
            return Response(
                {"error": f'Enviar {{"external_source": "...", "pairs": [[a, b], ...]}} (hasta {MAX_PAIRS} pares).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ext_ids = {x for p in pairs for x in p}
        issues = {
            r["external_id"]: r
            for r in Issue.objects.filter(
                workspace__slug=slug, external_source=source, external_id__in=ext_ids
            ).values("id", "external_id", "project_id", "workspace_id")
        }
        found, seen = [], set()
        for a, b in sorted(pairs):  # un par y su inverso: queda uno solo (dos dependencias opuestas serían un círculo)
            if a in issues and b in issues and frozenset((a, b)) not in seen:
                seen.add(frozenset((a, b)))
                found.append((issues[a], issues[b]))
        ids = {i["id"] for p in found for i in p}
        # all_objects: incluye las borradas a mano, para no volver a crearlas en cada corrida.
        linked, plain = set(), {}
        for pk, x, y, t, deleted in IssueRelation.all_objects.filter(
            Q(issue_id__in=ids) & Q(related_issue_id__in=ids)
        ).values_list("id", "issue_id", "related_issue_id", "relation_type", "deleted_at"):
            linked.add(frozenset((x, y)))
            if t == RELATES_TO and deleted is None:
                plain[frozenset((x, y))] = pk
        converted = 0
        if rtype == BLOCKED_BY:
            for a, b in found:
                pk = plain.pop(frozenset((a["id"], b["id"])), None)
                if pk is not None:
                    IssueRelation.objects.filter(pk=pk).update(
                        issue_id=a["id"], related_issue_id=b["id"], relation_type=BLOCKED_BY, updated_by=request.user)
                    converted += 1
        new = [
            IssueRelation(
                issue_id=a["id"],
                related_issue_id=b["id"],
                relation_type=rtype,
                project_id=a["project_id"],
                workspace_id=a["workspace_id"],
                created_by=request.user,
                updated_by=request.user,
            )
            for a, b in found
            if frozenset((a["id"], b["id"])) not in linked
        ]
        IssueRelation.objects.bulk_create(new, batch_size=500, ignore_conflicts=True)
        out = {"creadas": len(new), "ya_estaban": len(found) - len(new) - converted, "sin_tarea": len(pairs) - len(found)}
        if rtype == BLOCKED_BY:
            out["convertidas"] = converted
        return Response(out, status=status.HTTP_200_OK)
