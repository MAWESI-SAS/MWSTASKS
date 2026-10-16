# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Reglas automáticas por proyecto (solo web). Ver: admin y miembro. Crear, cambiar, apagar y borrar: solo admin
(afectan las tareas de todos)."""
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import Label, Project, State

from plane_mawesi import automations as A
from plane_mawesi import services
from plane_mawesi.models import Automation, TaskTemplate
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES

NOT_FOUND = Response({"error": "La regla no existe."}, status=status.HTTP_404_NOT_FOUND)


def rule_data(r):
    return {
        "id": str(r.id), "name": r.name, "enabled": r.enabled, "trigger": r.trigger, "trigger_value": r.trigger_value,
        "module_id": str(r.module_id) if r.module_id else None, "actions": r.actions, "runs": r.runs,
        "last_run_at": r.last_run_at,
    }


def _rules(slug, project_id):
    return Automation.objects.filter(workspace__slug=slug, project_id=project_id)


def _bad(error):
    return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)


class AutomationsEndpoint(PlaneSessionAPIView):
    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        scope = {"workspace__slug": slug, "project_id": project_id}
        return Response({
            "rules": [rule_data(r) for r in _rules(slug, project_id)],
            # Opciones para el formulario, en un solo pedido.
            "states": list(State.objects.filter(**scope).order_by("sequence").values("id", "name", "group")),
            "labels": list(Label.objects.filter(**scope).order_by("name").values("id", "name")),
            "templates": list(TaskTemplate.objects.filter(**scope).exclude(subtasks=[]).values("id", "name")),
        })

    def post(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        fields, error = A.parse_rule(request.data, slug, project_id)
        if error:
            return _bad(error)
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        rule = Automation.objects.create(project=project, workspace_id=project.workspace_id, **fields)
        return Response(rule_data(rule), status=status.HTTP_201_CREATED)


class AutomationDetailEndpoint(PlaneSessionAPIView):
    def patch(self, request, slug, project_id, rule_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        rule = _rules(slug, project_id).filter(pk=rule_id).first()
        if rule is None:
            return NOT_FOUND
        fields, error = A.parse_rule({**rule_data(rule), **request.data}, slug, project_id)
        if error:
            return _bad(error)
        for k, v in fields.items():
            setattr(rule, k, v)
        rule.save()
        return Response(rule_data(rule))

    def delete(self, request, slug, project_id, rule_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        _rules(slug, project_id).filter(pk=rule_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
