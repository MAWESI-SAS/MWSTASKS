# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Tipos de tarea del proyecto (admin edita, miembros leen) y tipo de cada tarea (web y API key)."""
from plane.app.permissions import ROLE
from plane.api.views.base import BaseAPIView as PlaneKeyAPIView
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import Issue, Project
from rest_framework import status
from rest_framework.response import Response

from plane_mawesi import services
from plane_mawesi import types as T
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES

MAX_BATCH = 500
NOT_FOUND = Response({"error": "No existe."}, status=status.HTTP_404_NOT_FOUND)


def _bad(e):
    return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


def _project(slug, project_id):
    return Project.objects.filter(workspace__slug=slug, pk=project_id).first()


def _issue_row(issue):
    row = T.effective(issue.project_id, [issue])[str(issue.id)]
    return {**row, "property_ids": T.visible_property_ids(row["type_id"])}


class TypesMixin:
    """GET lista de tipos / POST crea {name, color, description, is_default, property_ids, module_ids}."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        return Response(T.serialize(project_id))

    def post(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        project = _project(slug, project_id)
        if project is None:
            return NOT_FOUND
        try:
            t = T.save(project, request.data, request.user)
        except T.InvalidType as e:
            return _bad(e)
        return Response(next(x for x in T.serialize(project_id) if x["id"] == str(t.id)), status=status.HTTP_201_CREATED)


class TypeDetailMixin:
    def patch(self, request, slug, project_id, type_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        project, link = _project(slug, project_id), T.get_type(project_id, type_id)
        if project is None or link is None:
            return NOT_FOUND
        try:
            T.save(project, request.data, request.user, link.issue_type)
        except T.InvalidType as e:
            return _bad(e)
        return Response(next(x for x in T.serialize(project_id) if x["id"] == str(type_id)))

    def delete(self, request, slug, project_id, type_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        project, link = _project(slug, project_id), T.get_type(project_id, type_id)
        if project is None or link is None:
            return NOT_FOUND
        T.remove(project, link.issue_type)
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssueTypeMixin:
    """GET → {type_id, source, property_ids} / PUT {"type_id": id | null (automático)}."""

    def _issue(self, slug, project_id, issue_id):
        return Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk=issue_id).first()

    def get(self, request, slug, project_id, issue_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        issue = self._issue(slug, project_id, issue_id)
        return Response(_issue_row(issue)) if issue else NOT_FOUND

    def put(self, request, slug, project_id, issue_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        issue = self._issue(slug, project_id, issue_id)
        if issue is None:
            return NOT_FOUND
        try:
            T.set_issue_type(issue, request.data.get("type_id"), request.user.id)
        except T.InvalidType as e:
            return _bad(e)
        return Response(_issue_row(issue))


class IssueTypesBatchMixin:
    """GET ?issue_ids=a,b → {issue_id: {type_id, source}}."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        ids = [i for i in request.GET.get("issue_ids", "").split(",") if i][:MAX_BATCH]
        if not ids:
            return Response({})
        try:
            issues = list(Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk__in=ids).only("id", "type_id", "project_id"))
        except Exception:  # noqa: BLE001 - ids mal formados
            return Response({"error": "Ids inválidos."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(T.effective(project_id, issues))


class TypesEndpoint(TypesMixin, PlaneSessionAPIView):
    pass


class TypeDetailEndpoint(TypeDetailMixin, PlaneSessionAPIView):
    pass


class IssueTypeEndpoint(IssueTypeMixin, PlaneSessionAPIView):
    pass


class IssueTypesBatchEndpoint(IssueTypesBatchMixin, PlaneSessionAPIView):
    pass


class TypesKeyEndpoint(TypesMixin, PlaneKeyAPIView):
    pass


class IssueTypeKeyEndpoint(IssueTypeMixin, PlaneKeyAPIView):
    pass


class IssueTypesBatchKeyEndpoint(IssueTypesBatchMixin, PlaneKeyAPIView):
    pass
