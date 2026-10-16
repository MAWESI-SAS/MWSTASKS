# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from plane.db.models import Page, Project, ProjectMember, ProjectPage

from plane_mawesi.tests.conftest import ADMIN, GUEST, MEMBER, make_user


def url(ws, q=""):
    return f"/api/mawesi/workspaces/{ws.slug}/wiki/{'?q=' + q if q else ''}"


def page(project, owner, name, html, access=0):
    p = Page.objects.create(workspace=project.workspace, name=name, owned_by=owner, access=access, description_html=html)
    ProjectPage.objects.create(workspace=project.workspace, project=project, page=p)
    return p


@pytest.mark.django_db
class TestWiki:
    def test_busca_sin_tildes_en_titulo_y_texto(self, member_factory, workspace, project):
        user, c = member_factory("ana@example.com", MEMBER)
        page(project, user, "Conexiones Bases de Datos", "<p>Servidor de pruebas</p>")
        page(project, user, "Ayuda ERPTQ", "<p>Cómo hacer la conexión al ERP</p>")
        page(project, user, "Otra", "<p>nada</p>")
        names = [p["name"] for p in c.get(url(workspace, "conexion")).json()["pages"]]
        assert names == ["Ayuda ERPTQ", "Conexiones Bases de Datos"]
        hit = next(p for p in c.get(url(workspace, "conexion")).json()["pages"] if p["name"] == "Ayuda ERPTQ")
        assert "conexión" in hit["snippet"] and hit["project_identifier"] == "CON"

    def test_privadas_solo_su_dueno(self, member_factory, workspace, project):
        ana, c_ana = member_factory("ana@example.com", MEMBER)
        _, c_beto = member_factory("beto@example.com", MEMBER)
        page(project, ana, "Personal Docs", "<p>mío</p>", access=1)
        assert [p["name"] for p in c_ana.get(url(workspace)).json()["pages"]] == ["Personal Docs"]
        assert c_beto.get(url(workspace)).json()["pages"] == []

    def test_solo_proyectos_donde_es_miembro_y_no_invitados(self, member_factory, workspace, project, create_user):
        _, c = member_factory("ana@example.com", MEMBER)
        _, c_guest = member_factory("guest@example.com", GUEST)
        otro = Project.objects.create(name="Secreto", identifier="SEC", workspace=workspace, created_by=create_user)
        ProjectMember.objects.create(project=otro, workspace=workspace, member=create_user, role=ADMIN)
        page(otro, create_user, "No visible", "<p>x</p>")
        page(project, create_user, "Visible", "<p>x</p>")
        assert [p["name"] for p in c.get(url(workspace)).json()["pages"]] == ["Visible"]
        assert c_guest.get(url(workspace)).json()["pages"] == []

    def test_archivadas_no_aparecen(self, member_factory, workspace, project):
        user, c = member_factory("ana@example.com", MEMBER)
        p = page(project, user, "Vieja", "<p>x</p>")
        Page.objects.filter(pk=p.pk).update(archived_at="2026-01-01")
        assert c.get(url(workspace)).json()["pages"] == []

    def test_sin_sesion(self, workspace):
        from rest_framework.test import APIClient
        assert APIClient().get(url(workspace)).status_code in (401, 403)


def test_fragmento_separa_bloques():
    from plane_mawesi.views.wiki import snippet, text_of
    assert snippet(text_of("<h1>EBS</h1><p>Instructivo &amp; pasos</p>"), "") == "EBS Instructivo & pasos"
