# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Repetición de una tarea. Ver: admin y miembro. Cambiar o quitar: admin y miembro (igual que editar
la tarea en Plane)."""
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import Project

from plane_mawesi import recurrence as R
from plane_mawesi import services
from plane_mawesi.models import Recurrence, RecurrenceFrequency, RecurrenceTrigger
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES


def data_of(rule):
    if rule is None:
        return None
    start, target = R.next_dates(rule, rule.issue)
    return {
        "id": str(rule.id), "frequency": rule.frequency, "interval": rule.interval, "trigger": rule.trigger,
        "occurrences": rule.occurrences, "next_start": start.isoformat() if start else None,
        "next_target": target.isoformat() if target else None,
    }


def _bad(error):
    return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)


class IssueRecurrenceEndpoint(PlaneSessionAPIView):
    def _issue(self, request, slug, project_id, issue_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return None, FORBIDDEN
        issue = services.get_issue(slug, project_id, issue_id)
        if issue is None:
            return None, Response({"error": "No existe."}, status=status.HTTP_404_NOT_FOUND)
        return issue, None

    def get(self, request, slug, project_id, issue_id):
        issue, denied = self._issue(request, slug, project_id, issue_id)
        if denied:
            return denied
        return Response({"recurrence": data_of(Recurrence.objects.filter(issue=issue).select_related("issue").first())})

    def put(self, request, slug, project_id, issue_id):
        issue, denied = self._issue(request, slug, project_id, issue_id)
        if denied:
            return denied
        frequency, trigger = request.data.get("frequency"), request.data.get("trigger") or RecurrenceTrigger.COMPLETE
        try:
            interval = int(request.data.get("interval") or 1)
        except (TypeError, ValueError):
            interval = 0
        if frequency not in RecurrenceFrequency.values or trigger not in RecurrenceTrigger.values:
            return _bad("Frecuencia inválida.")
        if not 1 <= interval <= 30:
            return _bad("Elige un intervalo entre 1 y 30.")
        if trigger == RecurrenceTrigger.SCHEDULE and issue.target_date is None:
            return _bad("Para repetir en la fecha, la tarea necesita fecha de vencimiento.")
        rule = Recurrence.objects.filter(issue=issue).first()
        if rule is None:
            project = Project.objects.get(pk=project_id, workspace__slug=slug)
            rule = Recurrence(issue=issue, project=project, workspace_id=project.workspace_id)
        rule.frequency, rule.interval, rule.trigger = frequency, interval, trigger
        try:
            with transaction.atomic():
                rule.save()
        except IntegrityError:
            return _bad("La tarea ya se repite. Recarga la página.")
        rule.issue = issue
        return Response({"recurrence": data_of(rule)})

    def delete(self, request, slug, project_id, issue_id):
        issue, denied = self._issue(request, slug, project_id, issue_id)
        if denied:
            return denied
        Recurrence.objects.filter(issue=issue).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
