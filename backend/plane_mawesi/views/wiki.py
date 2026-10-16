# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Wiki: busca en las Páginas de todos los proyectos del usuario (Plane CE solo tiene Páginas por proyecto).

Mismas reglas de acceso que Plane: proyectos donde la persona es miembro activo (admin o miembro, como la Tabla),
sin proyectos archivados ni Páginas archivadas; las Páginas privadas solo las ve su dueño.
La búsqueda ignora mayúsculas y tildes ("conexion" encuentra "Conexión") en el título y el texto.
"""
import html
import re

from django.db.models import F, Func, Q, TextField, Value
from rest_framework.response import Response

from plane.app.permissions import ROLE
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import ProjectMember, ProjectPage, WorkspaceMember

from plane_mawesi.views.properties import READ_ROLES

MAX_RESULTS = 300
MAX_QUERY = 100
SNIPPET = 160
ACCENTED, PLAIN = "áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN"
TAG = re.compile(r"<[^>]+>")


def plain(text: str) -> str:
    return text.translate(str.maketrans(ACCENTED, PLAIN))


def no_accents(field: str) -> Func:
    return Func(F(field), Value(ACCENTED), Value(PLAIN), function="translate", output_field=TextField())


def text_of(description_html: str) -> str:
    """Texto de la Página con espacios entre bloques (description_stripped de Plane pega "Título" y "Párrafo")."""
    return html.unescape(TAG.sub(" ", description_html or ""))


def snippet(text: str, query: str) -> str:
    """Fragmento del texto alrededor de la primera coincidencia (o el comienzo si no hay búsqueda)."""
    text = " ".join((text or "").split())
    if not query:
        return text[:SNIPPET]
    pos = plain(text).lower().find(plain(query).lower())
    if pos < 0:
        return text[:SNIPPET]
    start = max(0, pos - SNIPPET // 3)
    return ("…" if start else "") + text[start:start + SNIPPET] + ("…" if start + SNIPPET < len(text) else "")


class WikiEndpoint(PlaneSessionAPIView):
    """GET ?q=texto → {pages: [{id, name, project_id, project_identifier, project_name, owned_by, updated_at,
    snippet}], truncated}."""

    def get(self, request, slug):
        is_ws_admin = WorkspaceMember.objects.filter(
            member=request.user, workspace__slug=slug, role=ROLE.ADMIN.value, is_active=True
        ).exists()
        members = ProjectMember.objects.filter(
            member=request.user, workspace__slug=slug, is_active=True, project__archived_at__isnull=True
        )
        if not is_ws_admin:
            members = members.filter(role__in=READ_ROLES)
        project_ids = list(members.values_list("project_id", flat=True))

        qs = ProjectPage.objects.filter(
            workspace__slug=slug, project_id__in=project_ids,
            page__deleted_at__isnull=True, page__archived_at__isnull=True,
        ).filter(Q(page__access=0) | Q(page__owned_by=request.user))
        query = (request.GET.get("q") or "").strip()[:MAX_QUERY]
        if query:
            needle = plain(query)
            qs = qs.annotate(
                plain_name=no_accents("page__name"), plain_text=no_accents("page__description_stripped")
            ).filter(Q(plain_name__icontains=needle) | Q(plain_text__icontains=needle))
        rows = list(
            qs.order_by("project__name", "page__name").values(
                "page_id", "page__name", "project_id", "project__identifier", "project__name",
                "page__owned_by_id", "page__updated_at", "page__description_html",
            )[: MAX_RESULTS + 1]
        )
        return Response({
            "truncated": len(rows) > MAX_RESULTS,
            "pages": [
                {
                    "id": str(r["page_id"]),
                    "name": r["page__name"] or "",
                    "project_id": str(r["project_id"]),
                    "project_identifier": r["project__identifier"],
                    "project_name": r["project__name"],
                    "owned_by": str(r["page__owned_by_id"]),
                    "updated_at": r["page__updated_at"],
                    "snippet": snippet(text_of(r["page__description_html"]), query),
                }
                for r in rows[:MAX_RESULTS]
            ],
        })
