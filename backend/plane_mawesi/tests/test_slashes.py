# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""La API responde igual sin la barra final, sin redirigir (ver slashes.py)."""
import pytest


@pytest.mark.django_db
class TestSinBarraFinal:
    def test_get_y_post_sin_barra(self, api_key_client, workspace, project):
        r = api_key_client.get(f"/api/workspaces/{workspace.slug}/projects")
        assert r.status_code == 200 and str(project.id) in {str(p["id"]) for p in r.json()}
        r = api_key_client.post(f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues", {"name": "Sin barra"},
                                format="json")
        assert r.status_code == 201, r.content
        assert api_key_client.get(f"/api/mawesi/workspaces/{workspace.slug}/projects/{project.id}/types").status_code == 200

    def test_lo_que_el_token_no_hace_sigue_negado(self, api_key_client, create_user):
        assert api_key_client.get("/api/users/api-tokens").status_code == 403
        assert api_key_client.delete("/api/users/me").status_code == 403
        create_user.refresh_from_db()
        assert create_user.is_active

    def test_lo_que_no_existe_sigue_siendo_404(self, api_key_client):
        assert api_key_client.get("/api/no-existe").status_code == 404
        assert api_key_client.get("/api/users/me/").status_code == 200  # con barra, igual que antes
