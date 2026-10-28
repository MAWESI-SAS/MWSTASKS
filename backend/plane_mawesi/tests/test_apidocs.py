# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Documentación de la API (/api/mawesi/docs/): completa, con permisos y al día con las rutas."""
import pytest
from rest_framework.test import APIClient

from plane_mawesi.apidocs_catalog import CATALOG

SCHEMA = "/api/mawesi/docs/schema/?format=json"
NO_DOC = {"/api/mawesi/ping/", "/api/mawesi/auth-providers/"}


@pytest.fixture
def schema(api_key_client):
    r = api_key_client.get(SCHEMA)
    assert r.status_code == 200, r.content[:300]
    return r.json()


def ops(schema):
    return [(m, p, o) for p, v in schema["paths"].items() for m, o in v.items()]


@pytest.mark.django_db
class TestDocumentacion:
    def test_solo_con_sesion_o_token(self, session_client):
        anon = APIClient()  # api_client y session_client son el mismo objeto en los fixtures de Plane
        assert anon.get(SCHEMA).status_code in (401, 403)
        assert anon.get("/api/mawesi/docs/").status_code in (401, 403)
        page = session_client.get("/api/mawesi/docs/")
        assert page.status_code == 200 and b"swagger-ui" in page.content

    def test_cubre_las_tres_familias(self, schema):
        paths = schema["paths"]
        assert len(ops(schema)) > 600
        assert "/api/workspaces/{slug}/projects/{project_id}/issues/" in paths  # web
        assert "/api/v1/workspaces/{slug}/projects/{project_id}/work-items/" in paths  # v1
        assert "/api/mawesi/workspaces/{slug}/projects/{project_id}/types/" in paths  # MAWESI
        assert not any(p.startswith(("/api/instances/", "/api/public/")) for p in paths)
        assert schema["components"]["securitySchemes"]["Token"]["name"] == "X-Api-Key"

    def test_cada_operacion_dice_quien_puede_y_tiene_etiqueta(self, schema):
        for m, p, o in ops(schema):
            assert "**Quién:**" in o["description"], (m, p)
            assert o["tags"] and o["summary"], (m, p)
        roles = {(m, p): o["description"] for m, p, o in ops(schema)}
        assert "Admins del proyecto" in roles[("post", "/api/workspaces/{slug}/projects/{project_id}/bulk-create-labels/")]

    def test_lo_que_el_token_no_hace_esta_marcado(self, schema):
        assert "Con token: no" in schema["paths"]["/api/users/api-tokens/"]["get"]["description"]
        assert "Con token: no" not in schema["paths"]["/api/users/me/"]["get"]["description"]
        assert "Con token: no" in schema["paths"]["/api/users/me/"]["delete"]["description"]

    def test_catalogo_mawesi_al_dia(self, schema):
        mawesi = {(m.upper(), p) for m, p, _ in ops(schema) if p.startswith("/api/mawesi/") and p not in NO_DOC}
        mawesi |= {(m.upper(), p.replace("/api/v1/mawesi/", "/api/mawesi/"))
                   for m, p, _ in ops(schema) if p.startswith("/api/v1/mawesi/")}
        catalog = {(m, "/api/mawesi/" + p) for m, p in CATALOG}
        assert mawesi - catalog == set(), "Rutas MAWESI sin documentar en apidocs_catalog.py"
        assert catalog - mawesi == set(), "apidocs_catalog.py documenta rutas que no existen"
        types = schema["paths"]["/api/mawesi/workspaces/{slug}/projects/{project_id}/types/"]["post"]
        assert types["summary"] == "Crear un tipo"
        assert types["requestBody"]["content"]["application/json"]["example"]["color"] == "red"
