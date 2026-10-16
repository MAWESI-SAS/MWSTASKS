# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Plantillas de tarea por proyecto. Solo web (sesión).
Ver y usar: admin y miembro. Crear: admin y miembro. Editar y borrar: admin o quien la creó."""
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from plane.app.permissions import ROLE
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import Module, Project
from plane.utils.host import base_host

from plane_mawesi import services
from plane_mawesi import templates as T
from plane_mawesi.models import TaskTemplate
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES

DUPLICATE = Response({"error": "Ya existe una plantilla con ese nombre."}, status=status.HTTP_400_BAD_REQUEST)
NOT_FOUND = Response({"error": "La plantilla no existe."}, status=status.HTTP_404_NOT_FOUND)


def template_data(t):
    return {
        "id": str(t.id), "name": t.name, "priority": t.priority, "module_id": str(t.module_id) if t.module_id else None,
        "assignee_ids": t.assignee_ids, "checklist": t.checklist, "subtasks": t.subtasks,
        "add_parent_name": t.add_parent_name, "created_by": str(t.created_by_id) if t.created_by_id else None,
    }


def _templates(slug, project_id):
    return TaskTemplate.objects.filter(workspace__slug=slug, project_id=project_id)


def _bad(error):
    return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)


class TemplatesEndpoint(PlaneSessionAPIView):
    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        return Response([template_data(t) for t in _templates(slug, project_id)])

    def post(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        fields, error = T.parse_template(request.data, slug, project_id)
        if error:
            return _bad(error)
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        try:
            with transaction.atomic():
                t = TaskTemplate.objects.create(project=project, workspace_id=project.workspace_id, **fields)
        except IntegrityError:
            return DUPLICATE
        return Response(template_data(t), status=status.HTTP_201_CREATED)


class TemplateDetailEndpoint(PlaneSessionAPIView):
    def _editable(self, request, slug, project_id, template_id):
        role = services.project_role(request.user, slug, project_id)
        t = _templates(slug, project_id).filter(pk=template_id).first()
        if role not in READ_ROLES:
            return None, FORBIDDEN
        if t is None:
            return None, NOT_FOUND
        if role != ROLE.ADMIN.value and t.created_by_id != request.user.id:
            return None, FORBIDDEN
        return t, None

    def patch(self, request, slug, project_id, template_id):
        t, denied = self._editable(request, slug, project_id, template_id)
        if denied:
            return denied
        fields, error = T.parse_template({**template_data(t), **request.data}, slug, project_id)
        if error:
            return _bad(error)
        for k, v in fields.items():
            setattr(t, k, v)
        try:
            with transaction.atomic():
                t.save()
        except IntegrityError:
            return DUPLICATE
        return Response(template_data(t))

    def delete(self, request, slug, project_id, template_id):
        t, denied = self._editable(request, slug, project_id, template_id)
        if denied:
            return denied
        t.delete()  # soft delete de Plane
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApplyTemplateEndpoint(PlaneSessionAPIView):
    """POST {issue_id} → agrega las subtareas a esa tarea. POST {name, module_id?} → crea la tarea y sus subtareas."""

    def post(self, request, slug, project_id, template_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        t = _templates(slug, project_id).filter(pk=template_id).first()
        if t is None:
            return NOT_FOUND
        parent, name, module_id = None, None, request.data.get("module_id") or None
        if request.data.get("issue_id"):
            parent = T.issue_of(slug, project_id, request.data["issue_id"])
            if parent is None:
                return _bad("La tarea no existe.")
            if not t.subtasks:
                return _bad("La plantilla no tiene subtareas.")
        else:
            name = str(request.data.get("name") or "").strip()
            if not name:
                return _bad("Escribe el nombre de la tarea.")
            if module_id and not Module.objects.filter(pk=module_id, project_id=project_id, workspace__slug=slug).exists():
                return _bad("La lista no es de este proyecto.")
        try:
            main, subs = T.apply(t, user=request.user, request_host=base_host(request=request, is_app=True),
                                 parent=parent, name=name, module_id=module_id)
        except ValidationError as e:
            return _bad(str(e.detail))
        return Response({"issue_id": str(main.id), "sequence_id": main.sequence_id, "subtasks": len(subs)},
                        status=status.HTTP_201_CREATED)
