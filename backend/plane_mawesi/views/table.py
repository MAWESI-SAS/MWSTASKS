# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Vista "Tabla" (como la de ClickUp): tareas del proyecto con horas y campos propios como columnas.

Un solo pedido arma todo en el servidor (Plane no trae los campos propios en sus listas).
"""
import collections
import uuid

from django.db.models import Sum
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import Issue, IssueAssignee, ModuleIssue, State

from plane_mawesi import properties as P
from plane_mawesi import services
from plane_mawesi.models import PropertyValue, Worklog
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES, _props

MAX_ROWS = 3000
CLOSED_GROUPS = ("completed", "cancelled")


class ProjectTableEndpoint(PlaneSessionAPIView):
    """GET ?module=<uuid>&closed=1 → {rows, truncated, states, properties}."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        qs = Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id)
        if request.GET.get("closed") != "1":
            qs = qs.exclude(state__group__in=CLOSED_GROUPS)
        module = request.GET.get("module")
        if module:
            try:
                uuid.UUID(module)
            except ValueError:
                return Response({"error": "Módulo inválido."}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(issue_module__module_id=module, issue_module__deleted_at__isnull=True)
        issues = list(
            qs.order_by("-sequence_id")
            .values("id", "sequence_id", "name", "state_id", "priority", "start_date", "target_date", "parent_id")[: MAX_ROWS + 1]
        )
        truncated = len(issues) > MAX_ROWS
        issues = issues[:MAX_ROWS]
        ids = [i["id"] for i in issues]

        assignees, modules, values = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(dict)
        for issue_id, user_id in IssueAssignee.objects.filter(issue_id__in=ids).values_list("issue_id", "assignee_id"):
            assignees[issue_id].append(str(user_id))
        for issue_id, module_id in ModuleIssue.objects.filter(issue_id__in=ids).values_list("issue_id", "module_id"):
            modules[issue_id].append(str(module_id))
        minutes = dict(
            Worklog.objects.filter(issue_id__in=ids).values("issue_id").annotate(t=Sum("duration_minutes")).values_list("issue_id", "t")
        )
        props = list(_props(slug, project_id))
        by_id = {p.id: (p, P.option_names(p)) for p in props}
        for r in PropertyValue.objects.filter(issue_id__in=ids, property_id__in=list(by_id)).values("issue_id", "property_id", "value"):
            prop, names = by_id[r["property_id"]]
            v = P.readable(prop, r["value"], names)
            if v is not None:
                values[r["issue_id"]][str(r["property_id"])] = v

        rows = [
            {
                **i,
                "id": str(i["id"]),
                "state_id": str(i["state_id"]) if i["state_id"] else None,
                "parent_id": str(i["parent_id"]) if i["parent_id"] else None,
                "assignee_ids": assignees.get(i["id"], []),
                "module_ids": modules.get(i["id"], []),
                "minutes": minutes.get(i["id"], 0),
                "values": values.get(i["id"], {}),
            }
            for i in issues
        ]
        states = {
            str(s["id"]): {"name": s["name"], "color": s["color"], "group": s["group"]}
            for s in State.objects.filter(project_id=project_id).values("id", "name", "color", "group")
        }
        properties = [
            {"id": str(p.id), "name": p.name, "type": p.type,
             "options": [{"id": str(o.id), "name": o.name, "color": o.color} for o in p.options.all()]}
            for p in props
        ]
        return Response({"rows": rows, "truncated": truncated, "states": states, "properties": properties},
                        status=status.HTTP_200_OK)
