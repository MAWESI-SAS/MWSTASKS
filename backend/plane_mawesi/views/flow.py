# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Flujo acumulado, lead/cycle time, rendimiento y envejecimiento de un proyecto."""
import uuid

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView as PlaneSessionAPIView

from plane_mawesi import flow as F
from plane_mawesi import services
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES


class ProjectFlowEndpoint(PlaneSessionAPIView):
    """GET ?days=14|30|90|180[&module=<uuid>] → ver flow.analyze."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        try:
            days = int(request.GET.get("days", 30))
        except ValueError:
            days = 0
        if days not in F.WINDOWS:
            return Response({"error": f"days debe ser uno de {F.WINDOWS}."}, status=status.HTTP_400_BAD_REQUEST)
        module = request.GET.get("module") or None
        if module:
            try:
                uuid.UUID(module)
            except ValueError:
                return Response({"error": "Lista inválida."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(F.analyze(project_id, days, timezone.now(), module_id=module))
