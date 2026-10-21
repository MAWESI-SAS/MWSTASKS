# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Logo del proyecto con imagen propia (Plane CE solo trae emoji o ícono).

La imagen queda en `logo_props.image = {"asset_id", "url"}`. `in_use`, `emoji` e `icon` de Plane no se tocan: un
cliente que no conoce `image` (apps, API) sigue mostrando el emoji o el ícono. Elegir un emoji o un ícono en Plane
reemplaza `logo_props` entero, así que también quita la imagen.

El archivo se guarda como FileAsset de tipo PROJECT_COVER (lo sirve `/api/assets/v2/static/<id>/`, igual que las
portadas) pero sin pasar por el flujo de subida de Plane, que lo pondría como portada del proyecto. Los logos
viejos se marcan borrados con `update(deleted_at=…)`: nunca `.delete()` (dispara un borrado en cascada).
"""
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import FileAsset, Project
from plane.settings.storage import S3Storage
from plane.utils.exception_logger import log_exception

from plane_mawesi import services

FORBIDDEN = Response({"error": "Solo un administrador del proyecto puede cambiar el logo."}, status=status.HTTP_403_FORBIDDEN)
NOT_FOUND = Response({"error": "El proyecto no existe."}, status=status.HTTP_404_NOT_FOUND)
# La web la achica a 256px antes de subir; este tope es para quien llame la API directo.
MAX_BYTES = 512 * 1024
# Se mira el contenido, no la extensión ni el Content-Type que manda el navegador. Sin SVG: puede llevar scripts.
SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
)


def sniff(head: bytes):
    """Tipo real del archivo por sus primeros bytes: (mime, extensión) o None."""
    for magic, mime, ext in SIGNATURES:
        if head.startswith(magic):
            return mime, ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def _project(request, slug, project_id):
    if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
        return None, FORBIDDEN
    project = Project.objects.filter(workspace__slug=slug, pk=project_id).select_related("workspace").first()
    return project, (None if project else NOT_FOUND)


def _retire(project, asset_id):
    if asset_id:
        FileAsset.objects.filter(pk=asset_id, project=project, deleted_at__isnull=True).update(deleted_at=timezone.now())


class ProjectLogoEndpoint(PlaneSessionAPIView):
    """POST (multipart `file`) sube o cambia la imagen / DELETE la quita. Solo admin del proyecto."""

    def post(self, request, slug, project_id):
        project, error = _project(request, slug, project_id)
        if error:
            return error
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"error": "Falta la imagen (campo `file`)."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_BYTES:
            return Response({"error": "La imagen pesa más de 512 KB."}, status=status.HTTP_400_BAD_REQUEST)
        kind = sniff(upload.read(12))
        upload.seek(0)
        if kind is None:
            return Response({"error": "Solo PNG, JPG o WebP."}, status=status.HTTP_400_BAD_REQUEST)
        mime, ext = kind
        name = f"{project.workspace_id}/{uuid.uuid4().hex}-project-logo.{ext}"
        # Sin `request`: con MinIO, S3Storage(request=…) apunta al host del navegador (sirve para firmar enlaces, no
        # para subir desde el servidor). upload_file solo atrapa ClientError; un error de conexión llega hasta acá.
        try:
            saved = S3Storage().upload_file(upload, name, content_type=mime)
        except Exception as e:  # noqa: BLE001
            log_exception(e)
            saved = False
        if not saved:
            return Response({"error": "No se pudo guardar la imagen."}, status=status.HTTP_502_BAD_GATEWAY)
        with transaction.atomic():
            asset = FileAsset.objects.create(
                asset=name,
                workspace_id=project.workspace_id,
                project=project,
                entity_type=FileAsset.EntityTypeContext.PROJECT_COVER,
                entity_identifier=str(project.id),
                attributes={"name": f"logo.{ext}", "type": mime, "size": upload.size, "mawesi": "project_logo"},
                size=upload.size,
                is_uploaded=True,
            )
            old = ((project.logo_props or {}).get("image") or {}).get("asset_id")
            project.logo_props = {**(project.logo_props or {}), "image": {"asset_id": str(asset.id), "url": asset.asset_url}}
            project.save(update_fields=["logo_props", "updated_at"])
            _retire(project, old)
        return Response({"logo_props": project.logo_props}, status=status.HTTP_200_OK)

    def delete(self, request, slug, project_id):
        project, error = _project(request, slug, project_id)
        if error:
            return error
        props = dict(project.logo_props or {})
        image = props.pop("image", None) or {}
        with transaction.atomic():
            project.logo_props = props
            project.save(update_fields=["logo_props", "updated_at"])
            _retire(project, image.get("asset_id"))
        return Response({"logo_props": project.logo_props}, status=status.HTTP_200_OK)
