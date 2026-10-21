# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Dependencias: las vistas de Plane que cambian el estado de una tarea o crean relaciones, con el control de
dependencias antes (ver plane_mawesi/dependencies.py). Se montan en urls.py ANTES que las de Plane, en las mismas rutas.

Respuesta cuando algo frena el cambio: 409 {"error": "...", "mawesi": "dependency_blocked", "blockers": [...]}. La web
(ext/dependencies/blocked-toast.ts) la muestra como aviso; Plane deshace solo el cambio que ya había pintado.
"""
from rest_framework import status
from rest_framework.response import Response

from plane.api.views import IssueDetailAPIEndpoint, IssueRelationListCreateAPIEndpoint
from plane.app.views import IssueRelationViewSet, IssueViewSet
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import Issue

from plane_mawesi import dependencies as D
from plane_mawesi import services
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES

MAX_BATCH = 500


def _blocked(request, slug, project_id, pk, via_api_key):
    new_state = request.data.get("state_id", request.data.get("state"))
    if not new_state:
        return None
    issue = Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk=pk).select_related("project").first()
    if issue is None:
        return None
    found = D.guard(issue, new_state, request.user, via_api_key=via_api_key)
    if not found:
        return None
    return Response({"error": D.message(found), "mawesi": "dependency_blocked", "blockers": found}, status=status.HTTP_409_CONFLICT)


def _cycle(request, slug, issue_id):
    """400 si la relación pedida cierra un ciclo de dependencias."""
    rtype = request.data.get("relation_type")
    if rtype not in D.REQUESTED:
        return None
    _, url_is_dependent = D.REQUESTED[rtype]
    issue = Issue.issue_objects.filter(workspace__slug=slug, pk=issue_id).first()
    if issue is None:
        return None
    for other in request.data.get("issues") or []:
        pred, succ = (other, issue.id) if url_is_dependent else (issue.id, other)
        if D.would_cycle(issue.workspace_id, pred, succ):
            return Response({"error": "Esa dependencia cierra un círculo: una tarea terminaría esperándose a sí misma.",
                             "mawesi": "dependency_cycle"}, status=status.HTTP_400_BAD_REQUEST)
    return None


# Los métodos de Plane llevan decoradores de permisos que leen slug/project_id de los argumentos con nombre.
class GuardedIssueViewSet(IssueViewSet):
    """Detalle de tarea de la web (tablero, lista, peek, detalle): PATCH/PUT con control de dependencias."""

    def partial_update(self, request, slug, project_id, pk=None):
        return _blocked(request, slug, project_id, pk, False) or super().partial_update(request, slug=slug, project_id=project_id, pk=pk)

    def update(self, request, slug, project_id, pk=None):
        return _blocked(request, slug, project_id, pk, False) or super().update(request, slug=slug, project_id=project_id, pk=pk)


class GuardedIssueDetailKeyEndpoint(IssueDetailAPIEndpoint):
    """Detalle de tarea de la API pública (empleados AI, integraciones)."""

    def patch(self, request, slug, project_id, pk):
        return _blocked(request, slug, project_id, pk, True) or super().patch(request, slug=slug, project_id=project_id, pk=pk)


class GuardedIssueRelationViewSet(IssueRelationViewSet):
    def create(self, request, slug, project_id, issue_id):
        return _cycle(request, slug, issue_id) or super().create(request, slug=slug, project_id=project_id, issue_id=issue_id)


class GuardedIssueRelationKeyEndpoint(IssueRelationListCreateAPIEndpoint):
    def post(self, request, slug, project_id, issue_id):
        return _cycle(request, slug, issue_id) or super().post(request, slug=slug, project_id=project_id, issue_id=issue_id)


class DependencyStatusEndpoint(PlaneSessionAPIView):
    """GET ?issue_ids=a,b → {issue_id: {"blocked_by": [...], "conflict": bool}} solo de las bloqueadas o con fechas
    que chocan (para las tarjetas)."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        ids = [i for i in request.GET.get("issue_ids", "").split(",") if i][:MAX_BATCH]
        if not ids:
            return Response({})
        try:
            issues = list(Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk__in=ids).select_related("state"))
        except Exception:  # noqa: BLE001 - ids mal formados
            return Response({"error": "Ids inválidos."}, status=status.HTTP_400_BAD_REQUEST)
        involved = {s for _, s, _ in D.edges_for([i.id for i in issues])}
        issues = [i for i in issues if i.id in involved]
        conflicts = D.date_conflicts(issues)
        out = {}
        for i in issues:
            group = i.state.group if i.state else "backlog"
            # Sin empezar: lo que no la deja empezar. En curso: lo que no la deja terminar.
            open_ = [] if group in D.RESOLVED else D.blockers(i, "completed" if group == "started" else "started")
            if open_ or str(i.id) in conflicts:
                out[str(i.id)] = {"blocked_by": open_, "conflict": str(i.id) in conflicts}
        return Response(out)
