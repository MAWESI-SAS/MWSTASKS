# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from plane.db.models import FileAsset, Project

from plane_mawesi.tests.conftest import MEMBER
from plane_mawesi.views.project_logo import MAX_BYTES

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64
EMOJI = {"in_use": "emoji", "emoji": {"value": "128512"}}


def url(project):
    return f"/api/mawesi/workspaces/{project.workspace.slug}/projects/{project.id}/logo/"


def upload(client, project, data=PNG, name="logo.png"):
    return client.post(url(project), {"file": SimpleUploadedFile(name, data)}, format="multipart")


@pytest.fixture
def storage(mocker):
    return mocker.patch("plane_mawesi.views.project_logo.S3Storage.upload_file", return_value=True)


@pytest.fixture
def with_emoji(project):
    Project.objects.filter(pk=project.pk).update(logo_props=EMOJI)
    project.refresh_from_db()
    return project


def active_logos(project):
    return FileAsset.objects.filter(project=project, attributes__mawesi="project_logo")


@pytest.mark.django_db
class TestLogoDelProyecto:
    def test_sube_imagen_y_conserva_emoji(self, session_client, with_emoji, storage):
        r = upload(session_client, with_emoji)
        assert r.status_code == 200, r.data
        asset = active_logos(with_emoji).get()
        assert r.data["logo_props"] == {**EMOJI, "image": {"asset_id": str(asset.id), "url": f"/api/assets/v2/static/{asset.id}/"}}
        assert asset.is_uploaded and asset.entity_type == "PROJECT_COVER"
        assert storage.call_args.kwargs["content_type"] == "image/png"
        with_emoji.refresh_from_db()
        assert with_emoji.cover_image_asset_id is None  # no pasa por el flujo de portada de Plane

    def test_cambiar_retira_el_logo_anterior(self, session_client, with_emoji, storage):
        upload(session_client, with_emoji)
        first = active_logos(with_emoji).get()
        r = upload(session_client, with_emoji, WEBP, "otro.webp")
        assert r.status_code == 200
        assert list(active_logos(with_emoji)) != [first]
        assert FileAsset.all_objects.get(pk=first.pk).deleted_at is not None
        assert storage.call_args.kwargs["content_type"] == "image/webp"

    @pytest.mark.parametrize("data,name", [
        (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "logo.svg"),
        (b"hola, no soy una imagen", "logo.png"),  # la extensión no alcanza: se mira el contenido
        (b"", "vacio.png"),
    ])
    def test_rechaza_lo_que_no_es_png_jpg_webp(self, session_client, with_emoji, storage, data, name):
        r = upload(session_client, with_emoji, data, name)
        assert r.status_code == 400
        storage.assert_not_called()

    def test_rechaza_imagen_grande(self, session_client, with_emoji, storage):
        r = upload(session_client, with_emoji, PNG + b"\x00" * MAX_BYTES)
        assert r.status_code == 400
        storage.assert_not_called()

    def test_solo_admin(self, member_factory, with_emoji, storage):
        _, member = member_factory("miembro@mawesi.co", MEMBER)
        assert upload(member, with_emoji).status_code == 403
        assert member.delete(url(with_emoji)).status_code == 403

    def test_falla_el_almacenamiento_no_cambia_nada(self, session_client, with_emoji, storage):
        storage.return_value = False
        assert upload(session_client, with_emoji).status_code == 502
        with_emoji.refresh_from_db()
        assert with_emoji.logo_props == EMOJI
        assert not active_logos(with_emoji).exists()

    def test_error_de_conexion_es_502(self, session_client, with_emoji, storage):
        storage.side_effect = ConnectionError("minio caído")
        assert upload(session_client, with_emoji).status_code == 502
        assert not active_logos(with_emoji).exists()

    def test_sube_por_el_endpoint_interno(self, session_client, with_emoji, mocker):
        # S3Storage(request=…) usaría el host del navegador: desde el contenedor no se llega.
        cls = mocker.patch("plane_mawesi.views.project_logo.S3Storage")
        cls.return_value.upload_file.return_value = True
        assert upload(session_client, with_emoji).status_code == 200
        cls.assert_called_once_with()

    def test_quitar_vuelve_al_emoji(self, session_client, with_emoji, storage):
        upload(session_client, with_emoji)
        asset = active_logos(with_emoji).get()
        r = session_client.delete(url(with_emoji))
        assert r.status_code == 200
        assert r.data["logo_props"] == EMOJI
        assert FileAsset.all_objects.get(pk=asset.pk).deleted_at is not None
