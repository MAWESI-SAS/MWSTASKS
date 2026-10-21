# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from plane.db.models import Label, State

from plane_mawesi.models import CardRule, StateLimit
from plane_mawesi.tests.conftest import ADMIN, MEMBER


def url(ws, project):
    return f"/api/mawesi/workspaces/{ws.slug}/projects/{project.id}/board/"


@pytest.mark.django_db
class TestBoardConfig:
    def test_admin_guarda_limites_y_reglas_y_miembro_lee(self, member_factory, workspace, project):
        _, admin = member_factory("admin@example.com", ADMIN)
        _, member = member_factory("ana@example.com", MEMBER)
        doing = State.objects.create(name="In Progress", group="started", project=project, workspace=workspace)
        bug = Label.objects.create(name="bug", project=project, workspace=workspace)
        body = {
            "limits": {str(doing.id): {"wip_limit": 3, "definition_of_done": "PR aprobado"}},
            "card_rules": [
                {"name": "Vencidas", "color": "red", "conditions": {"overdue": True}},
                {"name": "Bugs urgentes", "color": "orange", "conditions": {"priorities": ["urgent"], "label_ids": [str(bug.id)]}},
            ],
        }
        assert member.put(url(workspace, project), body, format="json").status_code == 403
        r = admin.put(url(workspace, project), body, format="json")
        assert r.status_code == 200, r.json()
        data = member.get(url(workspace, project)).json()
        assert data["limits"][str(doing.id)] == {"wip_limit": 3, "definition_of_done": "PR aprobado"}
        assert [x["name"] for x in data["card_rules"]] == ["Vencidas", "Bugs urgentes"]
        # Guardar de nuevo reemplaza todo (no se acumulan reglas)
        admin.put(url(workspace, project), {"limits": {}, "card_rules": body["card_rules"][:1]}, format="json")
        assert CardRule.objects.filter(project=project).count() == 1 and not StateLimit.objects.filter(project=project).exists()

    @pytest.mark.parametrize("rule", [
        {"name": "", "color": "red", "conditions": {"overdue": True}},
        {"name": "X", "color": "pink", "conditions": {"overdue": True}},
        {"name": "X", "color": "red", "conditions": {}},
        {"name": "X", "color": "red", "conditions": {"priorities": ["altisima"]}},
        {"name": "X", "color": "red", "conditions": {"due_in_days": 500}},
    ])
    def test_reglas_invalidas(self, member_factory, workspace, project, rule):
        _, admin = member_factory("admin@example.com", ADMIN)
        assert admin.put(url(workspace, project), {"card_rules": [rule]}, format="json").status_code == 400

    def test_columna_o_etiqueta_de_otro_proyecto(self, member_factory, workspace, project, create_user):
        from plane.db.models import Project

        _, admin = member_factory("admin@example.com", ADMIN)
        otro = Project.objects.create(name="Otro", identifier="OTR", workspace=workspace, created_by=create_user)
        ajeno = State.objects.create(name="Doing", group="started", project=otro, workspace=workspace)
        assert admin.put(url(workspace, project), {"limits": {str(ajeno.id): {"wip_limit": 2}}}, format="json").status_code == 400
        rule = {"name": "X", "color": "red", "conditions": {"state_ids": [str(ajeno.id)]}}
        assert admin.put(url(workspace, project), {"card_rules": [rule]}, format="json").status_code == 400
        assert admin.put(url(workspace, project), {"limits": {str(ajeno.id): {"wip_limit": 0}}}, format="json").status_code == 400
