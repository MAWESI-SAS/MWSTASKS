# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Login con Microsoft: Microsoft se simula (no sale a internet)."""
import base64
import json
from urllib.parse import parse_qs, urlparse

import pytest
from django.test import Client

from plane.db.models import Account, User
from plane.license.models import Instance

TENANT = "b9a9a3b9-ccb2-47dd-a72a-419fcae73a0c"
OTHER_TENANT = "11111111-2222-3333-4444-555555555555"


def id_token(**claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJub25lIn0.{body}.firma"


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


@pytest.fixture
def ms_env(monkeypatch, db, settings):
    settings.WEB_URL = "http://testserver"  # en producción viene del .env de Plane
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client-123")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secreto")
    monkeypatch.setenv("MICROSOFT_TENANT_ID", TENANT)
    monkeypatch.setenv("MICROSOFT_ALLOWED_DOMAINS", "mawesi.net")
    inst = Instance.objects.first() or Instance.objects.create(
        instance_name="t", instance_id="t", current_version="t", latest_version="t", last_checked_at="2026-01-01T00:00:00Z")
    inst.is_setup_done = True
    inst.save()


@pytest.fixture
def microsoft(monkeypatch):
    """Simula el token endpoint y Graph /me. Devuelve el dict para ajustar la respuesta por test."""
    state = {"tid": TENANT, "me": {"id": "oid-1", "mail": "Ana.Perez@mawesi.net", "userPrincipalName": "ana.perez@mawesi.net",
                                   "givenName": "Ana", "surname": "Pérez", "userType": "Member"}}
    calls = []

    def post(url, data=None, headers=None):
        calls.append(("post", url, data))
        return FakeResponse({"access_token": "at", "expires_in": 3600, "id_token": id_token(tid=state["tid"], oid="oid-1")})

    def get(url, headers=None):
        calls.append(("get", url, headers))
        return FakeResponse(state["me"])

    import plane.authentication.adapter.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod.requests, "post", post)
    monkeypatch.setattr(oauth_mod.requests, "get", get)
    state["calls"] = calls
    return state


def start(client):
    r = client.get("/auth/microsoft/?next_path=/mawesi/")
    assert r.status_code == 302
    return r


def finish(client, state=None):
    state = state or client.session["state"]
    return client.get(f"/auth/microsoft/callback/?code=abc&state={state}")


def error_code(response):
    return parse_qs(urlparse(response["Location"]).query).get("error_code", [None])[0]


@pytest.mark.django_db
def test_sin_configurar_no_hay_boton_y_avisa(monkeypatch, ms_env):
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "common")  # multi-tenant no se acepta
    c = Client(HTTP_USER_AGENT="pytest")
    assert c.get("/api/mawesi/auth-providers/").json() == {"microsoft": False}
    assert error_code(start(c)) == "5104"  # OAUTH_NOT_CONFIGURED


@pytest.mark.django_db
def test_inicio_redirige_al_tenant_con_state(ms_env):
    c = Client(HTTP_USER_AGENT="pytest")
    assert c.get("/api/mawesi/auth-providers/").json() == {"microsoft": True}
    loc = urlparse(start(c)["Location"])
    q = parse_qs(loc.query)
    assert loc.netloc == "login.microsoftonline.com" and loc.path == f"/{TENANT}/oauth2/v2.0/authorize"
    assert q["client_id"] == ["client-123"] and q["state"] == [c.session["state"]]
    assert q["redirect_uri"] == ["http://testserver/auth/microsoft/callback/"]
    assert "secreto" not in loc.query


@pytest.mark.django_db
def test_login_ok_crea_usuario_y_cuenta(ms_env, microsoft):
    c = Client(HTTP_USER_AGENT="pytest")
    start(c)
    r = finish(c)
    assert r.status_code == 302 and error_code(r) is None
    u = User.objects.get(email="ana.perez@mawesi.net")
    assert (u.first_name, u.last_name, u.is_password_autoset) == ("Ana", "Pérez", True)
    assert Account.objects.filter(user=u, provider="microsoft", provider_account_id="oid-1").exists()
    assert c.session.get("_auth_user_id") == str(u.id)
    token_call = next(x for x in microsoft["calls"] if x[0] == "post")
    assert token_call[1] == f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"
    # Segundo login: misma persona, no duplica
    c2 = Client(HTTP_USER_AGENT="pytest")
    start(c2)
    finish(c2)
    assert User.objects.filter(email="ana.perez@mawesi.net").count() == 1


@pytest.mark.django_db
def test_state_invalido_o_reusado_rechaza(ms_env, microsoft):
    c = Client(HTTP_USER_AGENT="pytest")
    start(c)
    assert error_code(finish(c, state="otro")) == "5999"
    assert not User.objects.filter(email="ana.perez@mawesi.net").exists()
    # El state se consume: repetir el callback con el state correcto tampoco entra
    start(c)
    good = c.session["state"]
    finish(c, good)
    assert error_code(finish(c, good)) == "5999"


@pytest.mark.django_db
@pytest.mark.parametrize("cambio", [
    {"tid": OTHER_TENANT},
    {"me": {"id": "x", "mail": "ana@mawesi.net", "userType": "Guest"}},
    {"me": {"id": "x", "mail": "ana@gmail.com", "userType": "Member"}},
    {"me": {"id": "x", "mail": None, "userPrincipalName": "ana_gmail.com#EXT#@mawesi.onmicrosoft.com", "userType": "Member"}},
])
def test_cuentas_no_permitidas(ms_env, microsoft, cambio):
    microsoft.update(cambio)
    c = Client(HTTP_USER_AGENT="pytest")
    start(c)
    r = finish(c)
    assert error_code(r) == "5999"
    assert "_auth_user_id" not in c.session
    assert not Account.objects.filter(provider="microsoft").exists()
