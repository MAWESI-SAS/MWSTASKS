# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""SLA por proyecto (plazo por prioridad en horas hábiles) y tiempo en cada estado."""
import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import Issue, IssueActivity, Module, ModuleIssue, Project

from plane_mawesi import services
from plane_mawesi import sla as S
from plane_mawesi.models import SlaPolicy
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES

MAX_BATCH = 500
MAX_HOURS = 2000


def policy_of(slug, project_id):
    return SlaPolicy.objects.filter(workspace__slug=slug, project_id=project_id).first()


def calendar_of(policy) -> S.Calendar:
    if policy is None:
        return S.Calendar()
    return S.Calendar(tz=policy.timezone, start=policy.work_start, end=policy.work_end,
                      workdays=tuple(policy.workdays), holidays=policy.colombia_holidays)


def policy_data(policy):
    if policy is None:
        return None
    return {
        "id": str(policy.id), "module_id": str(policy.module_id) if policy.module_id else None, "hours": policy.hours,
        "timezone": policy.timezone, "work_start": policy.work_start.strftime("%H:%M"),
        "work_end": policy.work_end.strftime("%H:%M"), "workdays": policy.workdays,
        "colombia_holidays": policy.colombia_holidays,
    }


def in_scope(policy, issue_ids):
    """Ids (str) a los que aplica la política: los del módulo, o todos si no tiene módulo."""
    if policy.module_id is None:
        return {str(i) for i in issue_ids}
    return {str(i) for i in ModuleIssue.objects.filter(module_id=policy.module_id, issue_id__in=issue_ids)
            .values_list("issue_id", flat=True)}


def sla_rows(policy, issues, now):
    cal = calendar_of(policy)
    return {
        str(i["id"]): S.sla_for(created_at=i["created_at"], priority=i["priority"], hours=policy.hours,
                                state_group=i["state__group"], completed_at=i["completed_at"], cal=cal, now=now)
        for i in issues
    }


def parse_policy(data, slug, project_id):
    """Valida el cuerpo del PUT. Devuelve (campos, error)."""
    hours = data.get("hours") or {}
    try:
        hours = {p: float(hours[p]) for p in S.PRIORITIES}
    except (KeyError, TypeError, ValueError):
        return None, "Falta el plazo de alguna prioridad."
    if any(h <= 0 or h > MAX_HOURS for h in hours.values()):
        return None, f"Cada plazo va entre 0 y {MAX_HOURS} horas."
    try:
        start = dt.time.fromisoformat(data.get("work_start") or "08:00")
        end = dt.time.fromisoformat(data.get("work_end") or "18:00")
    except ValueError:
        return None, "Horario en formato HH:MM."
    if start >= end:
        return None, "La hora de inicio va antes que la de fin."
    workdays = data.get("workdays", [0, 1, 2, 3, 4])
    if not isinstance(workdays, list) or not workdays or any(d not in range(7) for d in workdays):
        return None, "Elige al menos un día hábil."
    tz = data.get("timezone") or "America/Bogota"
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return None, "Zona horaria inválida."
    module_id = data.get("module_id") or None
    if module_id and not Module.objects.filter(pk=module_id, project_id=project_id, workspace__slug=slug).exists():
        return None, "La lista no es de este proyecto."
    return {"hours": hours, "work_start": start, "work_end": end, "workdays": sorted(set(workdays)), "timezone": tz,
            "module_id": module_id, "colombia_holidays": bool(data.get("colombia_holidays", True))}, None


class SlaPolicyEndpoint(PlaneSessionAPIView):
    """GET → {policy}; PUT (admin) crea o cambia; DELETE (admin) la quita."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        return Response({"policy": policy_data(policy_of(slug, project_id))})

    def put(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        fields, error = parse_policy(request.data, slug, project_id)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        policy = policy_of(slug, project_id)
        if policy is None:
            project = Project.objects.get(pk=project_id, workspace__slug=slug)
            policy = SlaPolicy(project=project, workspace_id=project.workspace_id, created_by=request.user)
        for k, v in fields.items():
            setattr(policy, k, v)
        policy.updated_by = request.user
        policy.save()
        return Response({"policy": policy_data(policy)})

    def delete(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        SlaPolicy.objects.filter(workspace__slug=slug, project_id=project_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SlaBatchEndpoint(PlaneSessionAPIView):
    """GET ?issue_ids=a,b → {issue_id: {status, due_at, remaining_minutes, ...}} solo para los que tienen SLA."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        policy = policy_of(slug, project_id)
        ids = [i for i in request.GET.get("issue_ids", "").split(",") if i][:MAX_BATCH]
        if policy is None or not ids:
            return Response({})
        try:
            scope = in_scope(policy, ids)
        except Exception:  # noqa: BLE001 - ids mal formados
            return Response({"error": "Ids inválidos."}, status=status.HTTP_400_BAD_REQUEST)
        issues = Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk__in=scope).values(
            "id", "created_at", "priority", "state__group", "completed_at")
        return Response(sla_rows(policy, issues, timezone.now()))


class IssueSlaEndpoint(PlaneSessionAPIView):
    """GET → {sla (o null si no aplica), states: tiempo en cada estado, policy}."""

    def get(self, request, slug, project_id, issue_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        issue = Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk=issue_id).select_related("state").first()
        if issue is None:
            return Response({"error": "No existe."}, status=status.HTTP_404_NOT_FOUND)
        policy = policy_of(slug, project_id)
        now = timezone.now()
        sla = None
        if policy is not None and in_scope(policy, [issue.id]):
            sla = sla_rows(policy, [{"id": issue.id, "created_at": issue.created_at, "priority": issue.priority,
                                     "state__group": issue.state.group if issue.state else "backlog",
                                     "completed_at": issue.completed_at}], now)[str(issue.id)]
        changes = IssueActivity.objects.filter(issue_id=issue.id, field="state", verb="updated").order_by("created_at")
        group = issue.state.group if issue.state else ""
        end = issue.completed_at if group == "completed" and issue.completed_at else now
        states = S.time_in_states(
            created_at=issue.created_at, current_state=issue.state.name if issue.state else "",
            changes=[(c.created_at, c.old_value, c.new_value) for c in changes if c.created_at <= end],
            now=end, cal=calendar_of(policy),
        )
        return Response({"sla": sla, "states": states, "policy": policy_data(policy)})
