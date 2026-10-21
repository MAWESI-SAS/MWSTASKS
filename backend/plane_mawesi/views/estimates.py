# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Estimado y restante en horas de un work item (web y API key: los empleados AI también estiman)."""
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView as PlaneKeyAPIView
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import Issue

from plane_mawesi import estimates as E
from plane_mawesi import services
from plane_mawesi.models import IssueEstimate
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES

MAX_BATCH = 500
NOT_FOUND = Response({"error": "El work item no existe."}, status=status.HTTP_404_NOT_FOUND)


def _issue_row(slug, project_id, issue):
    est = IssueEstimate.objects.filter(issue=issue).first()
    done = services.totals_by_issue(slug, project_id, [issue.id]).get(str(issue.id), 0)
    return E.row(est, done, issue.state.group if issue.state else "")


class IssueEstimateMixin:
    """GET → {original_minutes, remaining_minutes, remaining_is_manual, completed_minutes};
    PUT {"original_minutes"?, "remaining_minutes"?} (null borra) → lo mismo."""

    def get(self, request, slug, project_id, issue_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        issue = Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk=issue_id).select_related("state").first()
        if issue is None:
            return NOT_FOUND
        return Response(_issue_row(slug, project_id, issue))

    def put(self, request, slug, project_id, issue_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        issue = Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk=issue_id).select_related("state").first()
        if issue is None:
            return NOT_FOUND
        try:
            E.save(issue, request.data, request.user.id)
        except E.InvalidEstimate as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_issue_row(slug, project_id, issue))


class EstimatesBatchMixin:
    """GET ?issue_ids=a,b → {issue_id: fila} solo de las que tienen estimado (para las tarjetas)."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        ids = [i for i in request.GET.get("issue_ids", "").split(",") if i][:MAX_BATCH]
        if not ids:
            return Response({})
        try:
            issues = list(Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk__in=ids).values("id", "state__group"))
        except Exception:  # noqa: BLE001 - ids mal formados
            return Response({"error": "Ids inválidos."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(E.rows_for(slug, project_id, issues))


class IssueEstimateEndpoint(IssueEstimateMixin, PlaneSessionAPIView):
    pass


class EstimatesBatchEndpoint(EstimatesBatchMixin, PlaneSessionAPIView):
    pass


class IssueEstimateKeyEndpoint(IssueEstimateMixin, PlaneKeyAPIView):
    pass


class EstimatesBatchKeyEndpoint(EstimatesBatchMixin, PlaneKeyAPIView):
    pass
