# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""GET ?host=dev.azure.com → la imagen del ícono del sitio (404 si no tiene). Para los campos de tipo link."""
from django.core.cache import cache
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import WorkspaceMember

from plane_mawesi import favicons as F
from plane_mawesi.views.properties import FORBIDDEN

LOOKUPS_PER_MINUTE = 30


class FaviconEndpoint(PlaneSessionAPIView):
    def get(self, request, slug):
        if not WorkspaceMember.objects.filter(member=request.user, workspace__slug=slug, is_active=True).exists():
            return FORBIDDEN
        host = F.clean_host(request.GET.get("host", ""))
        if not host:
            return Response({"error": "Sitio inválido."}, status=status.HTTP_400_BAD_REQUEST)
        if cache.get(f"mawesi:favicon:{host}") is None:  # solo cuentan las búsquedas nuevas
            key = f"mawesi:favicon-lookups:{request.user.id}"
            if cache.get_or_set(key, 0, 60) >= LOOKUPS_PER_MINUTE:
                return Response({"error": "Demasiadas búsquedas, prueba en un minuto."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            cache.incr(key)
        found = F.icon(host)
        if not found:
            resp = HttpResponse(status=status.HTTP_404_NOT_FOUND)
            resp["Cache-Control"] = "private, max-age=86400"
            return resp
        body, kind = found
        resp = HttpResponse(body, content_type=kind)
        resp["Cache-Control"] = "private, max-age=604800"
        resp["X-Content-Type-Options"] = "nosniff"
        # Un SVG abierto directo no puede correr nada en nuestro dominio.
        resp["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
        return resp
