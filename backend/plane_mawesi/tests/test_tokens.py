# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""El token personal hace en la API de la web lo mismo que su dueño, con sus permisos (ver tokens.py)."""
import datetime

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from plane.api.rate_limit import ApiKeyRateThrottle
from plane.db.models import APIToken, Project, Workspace

from plane_mawesi.tests.conftest import GUEST, MEMBER


def client_for(user, **token_fields):
    token = APIToken.objects.create(user=user, label="test", **token_fields)
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=token.token)
    return c, token


@pytest.fixture(autouse=True)
def _sin_cupo_previo():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestTokenEnLaWeb:
    def test_el_token_entra_a_las_rutas_de_la_web_y_de_mawesi(self, api_key_client, workspace, project):
        r = api_key_client.get(f"/api/workspaces/{workspace.slug}/projects/")
        assert r.status_code == 200, r.content
        assert str(project.id) in {str(p["id"]) for p in r.json()}
        assert api_key_client.get(f"/api/mawesi/workspaces/{workspace.slug}/projects/{project.id}/types/").status_code == 200
        # /api/v1/ sigue igual
        assert api_key_client.get(f"/api/v1/workspaces/{workspace.slug}/projects/").status_code == 200

    def test_sin_token_ni_sesion_no_entra(self, api_client, workspace):
        assert api_client.get(f"/api/workspaces/{workspace.slug}/projects/").status_code in (401, 403)

    def test_token_vencido_o_apagado_no_entra(self, create_user, workspace):
        ayer = timezone.now() - datetime.timedelta(days=1)
        for fields in ({"expired_at": ayer}, {"is_active": False}):
            c, _ = client_for(create_user, **fields)
            assert c.get(f"/api/workspaces/{workspace.slug}/projects/").status_code in (401, 403)

    def test_la_sesion_de_la_web_sigue_andando(self, session_client, workspace):
        assert session_client.get(f"/api/workspaces/{workspace.slug}/projects/").status_code == 200


@pytest.mark.django_db
class TestMismosPermisosQueElDueno:
    def test_admin_edita_el_proyecto_y_miembro_no(self, create_user, member_factory, workspace, project):
        url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/"
        admin, _ = client_for(create_user)
        assert admin.patch(url, {"name": "Renombrado"}, format="json").status_code == 200
        ana, _ = member_factory("ana@example.com", MEMBER)
        miembro, _ = client_for(ana)
        assert miembro.patch(url, {"name": "Otro"}, format="json").status_code == 403
        assert Project.objects.get(pk=project.pk).name == "Renombrado"

    def test_mismas_reglas_en_las_rutas_mawesi(self, member_factory, workspace, project):
        url = f"/api/mawesi/workspaces/{workspace.slug}/projects/{project.id}/types/"
        ana, _ = member_factory("ana@example.com", MEMBER)
        miembro, _ = client_for(ana)
        assert miembro.get(url).status_code == 200
        assert miembro.post(url, {"name": "Bug"}, format="json").status_code == 403  # solo admins
        pepe, _ = member_factory("pepe@example.com", GUEST)
        invitado, _ = client_for(pepe)
        assert invitado.get(f"/api/mawesi/workspaces/{workspace.slug}/projects/{project.id}/sla/").status_code == 403

    def test_no_ve_workspaces_ajenos(self, create_user, api_key_client):
        from plane_mawesi.tests.conftest import make_user
        otro = Workspace.objects.create(name="Ajeno", slug="ajeno", owner=make_user("dueno@example.com"))
        assert api_key_client.get(f"/api/workspaces/{otro.slug}/projects/").status_code in (403, 404)

    def test_si_al_dueno_le_bajan_el_rol_el_token_baja_con_el(self, member_factory, workspace, project):
        from plane.db.models import ProjectMember, WorkspaceMember
        url = f"/api/mawesi/workspaces/{workspace.slug}/projects/{project.id}/types/"
        ana, _ = member_factory("ana@example.com", 20)
        c, _ = client_for(ana)
        assert c.post(url, {"name": "Bug"}, format="json").status_code == 201
        # Admin del workspace cuenta como admin del proyecto: se baja en los dos.
        ProjectMember.objects.filter(project=project, member=ana).update(role=MEMBER)
        WorkspaceMember.objects.filter(workspace=workspace, member=ana).update(role=MEMBER)
        assert c.post(url, {"name": "Mejora"}, format="json").status_code == 403


@pytest.mark.django_db
class TestLoQueElTokenNoHace:
    def test_no_maneja_tokens(self, api_key_client, api_token):
        assert api_key_client.get("/api/users/api-tokens/").status_code == 403
        assert api_key_client.post("/api/users/api-tokens/", {"label": "otro"}, format="json").status_code == 403
        assert api_key_client.delete(f"/api/users/api-tokens/{api_token.id}/").status_code == 403
        assert APIToken.objects.filter(user=api_token.user).count() == 1

    def test_no_desactiva_la_cuenta_ni_borra_el_workspace(self, api_key_client, create_user, workspace):
        assert api_key_client.delete("/api/users/me/").status_code == 403
        assert api_key_client.delete(f"/api/workspaces/{workspace.slug}/").status_code == 403
        create_user.refresh_from_db()
        assert create_user.is_active and Workspace.objects.filter(pk=workspace.pk).exists()
        assert api_key_client.get("/api/users/me/").status_code == 200  # leer el perfil sí

    def test_mismo_cupo_por_minuto_que_api_v1(self, api_key_client, workspace, monkeypatch):
        monkeypatch.setattr(ApiKeyRateThrottle, "rate", "3/minute")
        urls = [f"/api/workspaces/{workspace.slug}/projects/", f"/api/v1/workspaces/{workspace.slug}/projects/"]
        responses = [api_key_client.get(urls[i % 2]) for i in range(4)]
        assert [r.status_code for r in responses] == [200, 200, 200, 429]
        assert responses[0]["X-RateLimit-Remaining"] == "2"  # también en la ruta de la web
        assert responses[1]["X-RateLimit-Remaining"] == "1"


@pytest.mark.contract
def test_contrato_rutas_de_la_web_con_token():
    from django.urls import get_resolver

    from plane.app.views.base import BaseAPIView, BaseViewSet
    from plane.authentication.session import BaseSessionAuthentication
    from plane_mawesi.tokens import TokenAuthentication, accepts_session
    assert BaseSessionAuthentication in BaseAPIView.authentication_classes
    assert BaseSessionAuthentication in BaseViewSet.authentication_classes
    assert callable(TokenAuthentication.get_api_token) and callable(TokenAuthentication.validate_api_token)

    def walk(ps, pre=""):
        for p in ps:
            if hasattr(p, "url_patterns"):
                yield from walk(p.url_patterns, pre + str(p.pattern))
            else:
                yield pre + str(p.pattern), p.callback

    web = [(r, cb) for r, cb in walk(get_resolver().url_patterns)
           if r.startswith("api/") and not r.startswith(("api/v1/", "api/instances/", "api/public/"))]
    sin_token = [r for r, cb in web if accepts_session(cb)
                 and TokenAuthentication not in (getattr(cb, "initkwargs", None) or cb.view_initkwargs).get("authentication_classes", [])]
    assert sin_token == []
    assert len(web) > 250  # si Plane mueve sus rutas a otro prefijo, se nota acá
