# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Cronómetro (▶ de ClickUp). Uno por persona y workspace. Al pararlo se guarda como horas (Worklog)."""
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView as PlaneSessionAPIView

from plane_mawesi import services
from plane_mawesi.models import MAX_MINUTES_PER_ENTRY, Timer, Worklog
from plane_mawesi.serializers import WorklogSerializer
from plane_mawesi.views.worklogs import FORBIDDEN, WRITE_ROLES


def timer_data(timer):
    if timer is None:
        return None
    issue = timer.issue
    return {
        "id": str(timer.id), "started_at": timer.started_at, "description": timer.description,
        "issue_id": str(issue.id), "project_id": str(timer.project_id), "issue_name": issue.name,
        "issue_sequence": issue.sequence_id, "project_identifier": timer.project.identifier,
    }


def current(user, slug):
    return Timer.objects.filter(workspace__slug=slug, member=user).select_related("issue", "project").first()


def stop(timer, user):
    """Pasa el cronómetro a horas. Más de 24 h se parte en registros de 24 h (el máximo por registro)."""
    minutes = max(1, round((timezone.now() - timer.started_at).total_seconds() / 60))
    try:
        tz = ZoneInfo(user.user_timezone or "UTC")
    except (KeyError, ValueError):
        tz = ZoneInfo("UTC")
    day = timer.started_at.astimezone(tz).date()
    created = []
    with transaction.atomic():
        while minutes > 0:
            chunk = min(minutes, MAX_MINUTES_PER_ENTRY)
            worklog = Worklog.objects.create(
                issue_id=timer.issue_id, project_id=timer.project_id, workspace_id=timer.workspace_id,
                member=user, duration_minutes=chunk, date=day, description=timer.description, created_by=user,
            )
            services.record_activity(worklog=worklog, actor_id=user.id, verb="created")
            created.append(worklog)
            minutes -= chunk
        timer.delete(soft=False)
    return created


class CurrentTimerEndpoint(PlaneSessionAPIView):
    """GET → el cronómetro andando de quien consulta (o null). DELETE → lo descarta sin guardar horas."""

    def get(self, request, slug):
        return Response({"timer": timer_data(current(request.user, slug))}, status=status.HTTP_200_OK)

    def delete(self, request, slug):
        timer = current(request.user, slug)
        if timer is not None:
            timer.delete(soft=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StopTimerEndpoint(PlaneSessionAPIView):
    def post(self, request, slug):
        timer = current(request.user, slug)
        if timer is None:
            return Response({"error": "No hay un cronómetro andando."}, status=status.HTTP_404_NOT_FOUND)
        if "description" in request.data:
            timer.description = str(request.data.get("description") or "")[:2000]
        worklogs = stop(timer, request.user)
        return Response({"worklogs": WorklogSerializer(worklogs, many=True).data}, status=status.HTTP_200_OK)


class StartTimerEndpoint(PlaneSessionAPIView):
    """POST en una tarea. Si ya había otro andando, lo para y lo guarda (igual que ClickUp)."""

    def post(self, request, slug, project_id, issue_id):
        if services.project_role(request.user, slug, project_id) not in WRITE_ROLES:
            return FORBIDDEN
        issue = services.get_issue(slug, project_id, issue_id)
        if issue is None:
            return Response({"error": "El work item no existe."}, status=status.HTTP_404_NOT_FOUND)
        stopped = []
        previous = current(request.user, slug)
        if previous is not None:
            if previous.issue_id == issue.id:
                return Response({"timer": timer_data(previous), "stopped": []}, status=status.HTTP_200_OK)
            stopped = stop(previous, request.user)
        try:
            timer = Timer.objects.create(
                issue=issue, project_id=project_id, workspace_id=issue.workspace_id, member=request.user,
                started_at=timezone.now(), description=str(request.data.get("description") or "")[:2000],
                created_by=request.user,
            )
        except IntegrityError:  # dos clics a la vez: gana el primero
            timer = current(request.user, slug)
            if timer is None:
                return Response({"error": "No se pudo arrancar el cronómetro."}, status=status.HTTP_409_CONFLICT)
        return Response({"timer": timer_data(timer), "stopped": WorklogSerializer(stopped, many=True).data},
                        status=status.HTTP_201_CREATED)
