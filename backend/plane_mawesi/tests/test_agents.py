# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import base64
import io
import json
import sys

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from plane.db.models import APIToken, FileAsset, Issue, Project, ProjectMember, ProjectUserProperty, User, WorkspaceMember

from plane_mawesi.agents import Agent, TOKEN_LABEL, sync_agent
from plane_mawesi.tests.conftest import MEMBER

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
DIANA = {"email": "Diana@mawesi.dev", "name": "Diana Salazar", "title": "Analista de Facturación"}


@pytest.fixture
def storage(mocker):
    return mocker.patch("plane_mawesi.agents.S3Storage.upload_file", return_value=True)


@pytest.fixture
def otro(db, workspace, create_user):
    return Project.objects.create(name="Aurora", identifier="AUR", workspace=workspace, created_by=create_user)


def run(workspace, agents, *extra):
    out, err = io.StringIO(), io.StringIO()
    stdin = io.StringIO(json.dumps(agents))
    old, sys.stdin = sys.stdin, stdin
    try:
        call_command("mawesi_agents", "--workspace", workspace.slug, *extra, stdout=out, stderr=err)
    finally:
        sys.stdin = old
    return [json.loads(line) for line in out.getvalue().splitlines()], err.getvalue()


@pytest.mark.django_db
class TestEmpleadosAI:
    def test_crea_usuario_normal_con_token_y_proyectos(self, workspace, project, otro):
        tokens, _ = run(workspace, [DIANA])
        u = User.objects.get(email="diana@mawesi.dev")
        assert (u.first_name, u.last_name, u.display_name) == ("Diana", "Salazar", "diana")
        # Usuario normal: Plane esconde a los bots de responsables, búsqueda y reportes.
        assert not u.is_bot and u.is_active and not u.has_usable_password()
        wm = WorkspaceMember.objects.get(workspace=workspace, member=u)
        assert (wm.role, wm.is_active, wm.company_role) == (MEMBER, True, "Analista de Facturación")
        assert set(ProjectMember.objects.filter(member=u, is_active=True).values_list("project__identifier", flat=True)) == {"CON", "AUR"}
        assert ProjectUserProperty.objects.filter(user=u).count() == 2
        assert tokens == [{"email": "diana@mawesi.dev", "token": APIToken.objects.get(user=u, is_active=True).token}]

    def test_el_token_actua_como_el_empleado(self, workspace, project):
        tokens, _ = run(workspace, [DIANA])
        c = APIClient()
        c.credentials(HTTP_X_API_KEY=tokens[0]["token"])
        r = c.post(f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-items/", {"name": "Facturar"}, format="json")
        assert r.status_code == 201, r.data
        assert Issue.objects.get(pk=r.data["id"]).created_by.email == "diana@mawesi.dev"

    def test_repetir_no_cambia_nada(self, workspace, project, storage):
        agente = {**DIANA, "avatar_b64": base64.b64encode(PNG).decode()}
        run(workspace, [agente])
        tokens, err = run(workspace, [agente])
        assert tokens == [] and "ya existía" in err and "avatar igual" in err
        assert storage.call_count == 1
        assert User.objects.filter(email="diana@mawesi.dev").count() == 1
        assert APIToken.objects.filter(label=TOKEN_LABEL, is_active=True).count() == 1

    def test_solo_los_proyectos_pedidos(self, workspace, project, otro):
        run(workspace, [{**DIANA, "projects": ["aur"]}])
        assert list(ProjectMember.objects.filter(member__email="diana@mawesi.dev").values_list("project__identifier", flat=True)) == ["AUR"]

    def test_proyecto_inexistente_falla_sin_crear_nada(self, workspace, project):
        with pytest.raises(ValueError):
            sync_agent(workspace, Agent.from_dict({**DIANA, "projects": ["NOPE"]}))
        assert not User.objects.filter(email="diana@mawesi.dev").exists()

    def test_avatar_como_plane(self, workspace, project, storage):
        run(workspace, [{**DIANA, "avatar_b64": base64.b64encode(PNG).decode()}])
        u = User.objects.get(email="diana@mawesi.dev")
        assert u.avatar_asset.entity_type == "USER_AVATAR" and u.avatar_asset.workspace_id is None
        assert u.avatar_url == f"/api/assets/v2/static/{u.avatar_asset_id}/"
        assert storage.call_args.kwargs["content_type"] == "image/png"

    def test_avatar_nuevo_retira_el_anterior(self, workspace, project, storage):
        run(workspace, [{**DIANA, "avatar_b64": base64.b64encode(PNG).decode()}])
        first = User.objects.get(email="diana@mawesi.dev").avatar_asset_id
        run(workspace, [{**DIANA, "avatar_b64": base64.b64encode(PNG + b"\x01").decode()}])
        assert FileAsset.all_objects.get(pk=first).deleted_at is not None
        assert User.objects.get(email="diana@mawesi.dev").avatar_asset_id != first

    def test_avatar_que_no_es_imagen_falla(self, workspace, project, storage):
        with pytest.raises(ValueError):
            run(workspace, [{**DIANA, "avatar_b64": base64.b64encode(b"<svg/>").decode()}])
        storage.assert_not_called()

    def test_rotar_desactiva_el_token_viejo(self, workspace, project):
        viejo = run(workspace, [DIANA])[0][0]["token"]
        nuevo = run(workspace, [DIANA], "--rotate")[0][0]["token"]
        assert nuevo != viejo
        assert not APIToken.objects.get(token=viejo).is_active and APIToken.objects.get(token=nuevo).is_active

    def test_baja_conserva_lo_hecho_y_corta_el_token(self, workspace, project):
        token = run(workspace, [DIANA])[0][0]["token"]
        run(workspace, [{**DIANA, "active": False}])
        u = User.objects.get(email="diana@mawesi.dev")
        assert not u.is_active and not APIToken.objects.get(token=token).is_active
        assert not WorkspaceMember.objects.get(member=u).is_active
        c = APIClient()
        c.credentials(HTTP_X_API_KEY=token)
        # Plane responde 403 (no 401) a un token desactivado: DRF no manda WWW-Authenticate.
        assert c.get(f"/api/v1/workspaces/{workspace.slug}/projects/").status_code == 403

    def test_no_toca_a_una_persona_con_el_mismo_correo(self, workspace, project, create_user):
        antes = (create_user.first_name, WorkspaceMember.objects.get(workspace=workspace, member=create_user).role)
        with pytest.raises(ValueError):
            run(workspace, [{"email": create_user.email, "name": "Otro Nombre"}])
        create_user.refresh_from_db()
        assert (create_user.first_name, WorkspaceMember.objects.get(workspace=workspace, member=create_user).role) == antes
        assert not APIToken.objects.filter(user=create_user, label=TOKEN_LABEL).exists()
