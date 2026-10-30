# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Borrar archivos de una tarea: Admin, Member o quien lo subió; Guest no (ver views/attachments.py)."""
import pytest

from plane.db.models import FileAsset

from plane_mawesi.tests.conftest import GUEST, MEMBER

V2 = "/api/assets/v2/workspaces/{slug}/projects/{project}/issues/{issue}/attachments/{pk}/"


@pytest.fixture(autouse=True)
def _sin_cola(monkeypatch):
    calls = []
    monkeypatch.setattr("plane.app.views.issue.attachment.issue_activity.delay", lambda **kw: calls.append(kw))
    return calls


def archivo(issue, user, name="informe.pdf"):
    a = FileAsset.objects.create(
        attributes={"name": name, "type": "application/pdf", "size": 10}, asset=f"x/{name}", size=10,
        workspace=issue.workspace, project=issue.project, issue=issue,
        entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT, is_uploaded=True)
    FileAsset.objects.filter(pk=a.pk).update(created_by=user)  # save() de Plane pone el usuario del pedido (acá, ninguno)
    return a


def url(tpl, issue, asset):
    return tpl.format(slug=issue.workspace.slug, project=issue.project_id, issue=issue.id, pk=asset.id)


@pytest.mark.django_db
class TestBorrarArchivos:
    def test_member_borra_un_archivo_que_subio_otro(self, issue, create_user, member_factory, _sin_cola):
        a = archivo(issue, create_user)  # lo "subió" el admin (como la migración de ClickUp)
        _, ximena = member_factory("ximena@example.com", MEMBER)
        r = ximena.delete(url(V2, issue, a))
        assert r.status_code == 204, r.content
        a = FileAsset.all_objects.get(pk=a.pk)
        assert a.deleted_at is not None and a.is_deleted
        assert _sin_cola and _sin_cola[-1]["type"] == "attachment.activity.deleted"  # queda en el historial

    def test_guest_no_borra_lo_ajeno_pero_si_lo_suyo(self, issue, create_user, member_factory):
        pepe, invitado = member_factory("pepe@example.com", GUEST)
        ajeno, suyo = archivo(issue, create_user, "a.pdf"), archivo(issue, pepe, "b.pdf")
        assert invitado.delete(url(V2, issue, ajeno)).status_code == 403
        assert FileAsset.objects.filter(pk=ajeno.pk).exists()
        assert invitado.delete(url(V2, issue, suyo)).status_code == 204

    def test_la_ruta_vieja_que_borra_para_siempre_sigue_como_en_plane(self, issue, create_user, member_factory):
        a = archivo(issue, create_user)
        _, ximena = member_factory("ximena@example.com", MEMBER)
        vieja = f"/api/workspaces/{issue.workspace.slug}/projects/{issue.project_id}/issues/{issue.id}/issue-attachments/{a.id}/"
        assert ximena.delete(vieja).status_code == 403
        assert FileAsset.objects.filter(pk=a.pk).exists()

    def test_listar_sigue_siendo_de_plane(self, issue, create_user, member_factory):
        archivo(issue, create_user)
        _, ximena = member_factory("ximena@example.com", MEMBER)
        r = ximena.get(f"/api/assets/v2/workspaces/{issue.workspace.slug}/projects/{issue.project_id}/issues/{issue.id}/attachments/")
        assert r.status_code == 200 and len(r.json()) == 1


@pytest.mark.contract
def test_contrato_borrado_de_archivos_de_plane():
    """Si Plane cambia el borrado (sin `__wrapped__` o con otros parámetros), esto avisa antes de deployar."""
    import inspect

    from django.urls import resolve

    from plane.app.views.issue.attachment import IssueAttachmentV2Endpoint

    inner = IssueAttachmentV2Endpoint.delete.__wrapped__
    assert list(inspect.signature(inner).parameters) == ["self", "request", "slug", "project_id", "issue_id", "pk"]
    x = "00000000-0000-0000-0000-000000000000"
    assert resolve(f"/api/assets/v2/workspaces/w/projects/{x}/issues/{x}/attachments/{x}/").func.view_class.__module__ == "plane_mawesi.views.attachments"
