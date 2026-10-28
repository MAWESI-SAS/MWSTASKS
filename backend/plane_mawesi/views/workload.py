# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Carga de trabajo del workspace (la vista Workload de ClickUp). Ver workload.py."""
import datetime as dt
import uuid

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import WorkspaceMember

from plane_mawesi import workload as W
from plane_mawesi.recurrence import today as _today
from plane_mawesi.views.properties import FORBIDDEN

DEFAULT_DAYS = 14


def _bad(error):
    return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)


def _uuids(raw):
    out = []
    for v in (raw or "").split(","):
        v = v.strip()
        if v:
            uuid.UUID(v)
            out.append(v)
    return out


class WorkloadEndpoint(PlaneSessionAPIView):
    """GET ?from=AAAA-MM-DD&to=AAAA-MM-DD[&project=a,b][&module=<uuid>] → filas por persona con minutos y tareas por día,
    capacidad, tareas de cada celda y lo sin programar. Sin fechas: dos semanas desde el lunes de esta semana."""

    def get(self, request, slug):
        if not WorkspaceMember.objects.filter(member=request.user, workspace__slug=slug, is_active=True,
                                              role__in=(ROLE.ADMIN.value, ROLE.MEMBER.value)).exists():
            return FORBIDDEN
        today = _today()
        try:
            start = dt.date.fromisoformat(request.GET["from"]) if request.GET.get("from") else today - dt.timedelta(days=today.weekday())
            end = dt.date.fromisoformat(request.GET["to"]) if request.GET.get("to") else start + dt.timedelta(days=DEFAULT_DAYS - 1)
        except ValueError:
            return _bad("Fechas en formato AAAA-MM-DD.")
        try:
            projects = _uuids(request.GET.get("project"))
            module = _uuids(request.GET.get("module"))
        except ValueError:
            return _bad("Proyecto o lista inválidos.")
        try:
            return Response(W.report(request.user, slug, start, end, today, project_ids=projects or None,
                                     module_id=module[0] if module else None))
        except W.InvalidWorkload as e:
            return _bad(str(e))


class WorkloadCapacityEndpoint(PlaneSessionAPIView):
    """PUT {"member_id", "hours_per_day"}: horas por día de una persona (0 a 24). Solo admins del workspace."""

    def put(self, request, slug):
        if not WorkspaceMember.objects.filter(member=request.user, workspace__slug=slug, is_active=True, role=ROLE.ADMIN.value).exists():
            return FORBIDDEN
        member_id = str(request.data.get("member_id") or "")
        try:
            uuid.UUID(member_id)
            return Response(W.set_capacity(slug, member_id, request.data.get("hours_per_day"), request.user))
        except ValueError as e:
            return _bad(str(e) if isinstance(e, W.InvalidWorkload) else "Persona inválida.")
