# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Capacidad por ciclo (solo web)."""
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import Cycle

from plane_mawesi import capacity as C
from plane_mawesi import services
from plane_mawesi.recurrence import today as _today
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES


class CycleListEndpoint(PlaneSessionAPIView):
    """GET → {cycles: [{id, name, start, end}], current_id}: ciclos con fechas, del más nuevo al más viejo."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        today = _today()
        cycles, current = [], None
        for c in Cycle.objects.filter(workspace__slug=slug, project_id=project_id, archived_at__isnull=True).order_by("-start_date"):
            dates = C.cycle_dates(c)
            if dates is None:
                continue
            cycles.append({"id": str(c.id), "name": c.name, "start": dates[0].isoformat(), "end": dates[1].isoformat()})
            if current is None and dates[0] <= today <= dates[1]:
                current = str(c.id)
        return Response({"cycles": cycles, "current_id": current or (cycles[0]["id"] if cycles else None)})


class CycleCapacityEndpoint(PlaneSessionAPIView):
    """GET → reporte de capacidad; PUT → guarda horas por día y días libres (ver capacity.save)."""

    def _cycle(self, slug, project_id, cycle_id):
        return Cycle.objects.filter(workspace__slug=slug, project_id=project_id, pk=cycle_id).first()

    def get(self, request, slug, project_id, cycle_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        cycle = self._cycle(slug, project_id, cycle_id)
        if cycle is None:
            return Response({"error": "El ciclo no existe."}, status=status.HTTP_404_NOT_FOUND)
        try:
            return Response(C.report(cycle, _today()))
        except C.InvalidCapacity as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, slug, project_id, cycle_id):
        role = services.project_role(request.user, slug, project_id)
        if role not in READ_ROLES:
            return FORBIDDEN
        cycle = self._cycle(slug, project_id, cycle_id)
        if cycle is None:
            return Response({"error": "El ciclo no existe."}, status=status.HTTP_404_NOT_FOUND)
        try:
            C.save(cycle, request.data, request.user, is_admin=role == ROLE.ADMIN.value)
            return Response(C.report(cycle, _today()))
        except PermissionError:
            return FORBIDDEN
        except C.InvalidCapacity as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
