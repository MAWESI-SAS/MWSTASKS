# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Relaciones "relacionada con" en lote, por id externo (migración y copia incremental desde ClickUp).

La API v1 de Plane crea relaciones de a un work item por pedido y dispara un aviso por cada una. Acá:
- un pedido trae hasta MAX_PAIRS pares de ids externos, de cualquier proyecto del workspace;
- solo crea lo que falta: si ya hay una relación entre las 2 tareas (de cualquier tipo, en cualquier sentido,
  o borrada a mano en MWSTASKS) no se toca;
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
FORBIDDEN = Response({"error": "No tienes permiso para esto."}, status=status.HTTP_403_FORBIDDEN)


def _pairs(raw):
    """[[a, b], ...] -> set de pares ordenados (sin repetidos ni una tarea consigo misma). None si el formato no sirve."""
    if not isinstance(raw, list) or len(raw) > MAX_PAIRS:
        return None
    out = set()
    for p in raw:
        if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(isinstance(x, str) and x for x in p):
            return None
        a, b = p
        if a != b:
            out.add((min(a, b), max(a, b)))
    return out


class RelationsBatchKeyEndpoint(PlaneKeyAPIView):
    """POST {"external_source": "clickup", "pairs": [[ext_a, ext_b], ...]} -> {"creadas", "ya_estaban", "sin_tarea"}.
    Solo admins del workspace: las relaciones cruzan proyectos."""

    def post(self, request, slug):
        if not WorkspaceMember.objects.filter(
            member=request.user, workspace__slug=slug, role=ROLE.ADMIN.value, is_active=True
        ).exists():
            return FORBIDDEN
        source = request.data.get("external_source")
        pairs = _pairs(request.data.get("pairs"))
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
        found = [(issues[a], issues[b]) for a, b in pairs if a in issues and b in issues]
        ids = {i["id"] for p in found for i in p}
        # all_objects: incluye las borradas a mano, para no volver a crearlas en cada corrida.
        linked = set()
        for x, y in IssueRelation.all_objects.filter(
            Q(issue_id__in=ids) & Q(related_issue_id__in=ids)
        ).values_list("issue_id", "related_issue_id"):
            linked.add(frozenset((x, y)))
        new = [
            IssueRelation(
                issue_id=a["id"],
                related_issue_id=b["id"],
                relation_type=RELATES_TO,
                project_id=a["project_id"],
                workspace_id=a["workspace_id"],
                created_by=request.user,
                updated_by=request.user,
            )
            for a, b in found
            if frozenset((a["id"], b["id"])) not in linked
        ]
        IssueRelation.objects.bulk_create(new, batch_size=500, ignore_conflicts=True)
        return Response(
            {"creadas": len(new), "ya_estaban": len(found) - len(new), "sin_tarea": len(pairs) - len(found)},
            status=status.HTTP_200_OK,
        )
