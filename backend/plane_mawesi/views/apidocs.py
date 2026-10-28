# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Página de la documentación de la API (Swagger UI) y el schema OpenAPI (JSON o YAML). Ver plane_mawesi/apidocs.py.

El schema es igual para todos: se arma una vez por proceso (tarda unos segundos). Solo para usuarios con sesión o
token; urls.py (tokens.with_tokens) les suma el token como a toda ruta de la web.

Al armarlo, drf-spectacular llama a `get_queryset()` de cada vista sin un pedido real y Plane registra cada falla como
ERROR en `plane.exception` (decenas de líneas falsas). Mientras se arma, ese logger calla solo en este hilo.
"""
import logging
import threading

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from plane.authentication.session import BaseSessionAuthentication

_cache = {}
_building = threading.local()


class _QuietWhileBuilding(logging.Filter):
    def filter(self, record):
        return not getattr(_building, "on", False)


logging.getLogger("plane.exception").addFilter(_QuietWhileBuilding())


class ApiSchemaEndpoint(SpectacularAPIView):
    authentication_classes = [BaseSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_schema_response(self, request):
        if "schema" not in _cache:  # el mismo para JSON y YAML: cambia solo cómo se dibuja
            _building.on = True
            try:
                _cache["schema"] = super()._get_schema_response(request).data
            finally:
                _building.on = False
        return Response(_cache["schema"])


class ApiDocsEndpoint(SpectacularSwaggerView):
    authentication_classes = [BaseSessionAuthentication]
    permission_classes = [IsAuthenticated]
    url_name = "mawesi-api-schema"
