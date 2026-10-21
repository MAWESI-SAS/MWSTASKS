# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Configuración del tablero: límites WIP, definición de terminado y colores de tarjeta (solo web)."""
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import Project

from plane_mawesi import board as B
from plane_mawesi import services
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES


class BoardConfigEndpoint(PlaneSessionAPIView):
    """GET → {limits: {state_id: {wip_limit, definition_of_done}}, card_rules: [...]}; PUT (admin) lo reemplaza."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        return Response(B.config(project_id))

    def put(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        project = Project.objects.filter(pk=project_id, workspace__slug=slug).first()
        if project is None:
            return Response({"error": "El proyecto no existe."}, status=status.HTTP_404_NOT_FOUND)
        try:
            return Response(B.save(project, request.data, request.user))
        except B.InvalidBoard as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
