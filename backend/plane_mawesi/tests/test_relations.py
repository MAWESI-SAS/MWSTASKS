# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import pytest
from rest_framework.test import APIClient

from plane.db.models import APIToken, Issue, IssueRelation, Project, ProjectMember

from plane_mawesi.tests.conftest import ADMIN, MEMBER
from plane_mawesi.views.relations import MAX_PAIRS


def url(ws):
    return f"/api/v1/mawesi/workspaces/{ws.slug}/relations/"


@pytest.fixture
def tasks(db, workspace, project, create_user):
    """5 tareas con id externo: 3 en el proyecto, 2 en otro proyecto del mismo workspace."""
    other = Project.objects.create(name="Otro", identifier="OTR", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(project=other, workspace=workspace, member=create_user, role=ADMIN)
    out = {}
    for ext, p in (("a", project), ("b", project), ("c", project), ("x", other), ("y", other)):
        out[ext] = Issue.objects.create(name=ext, project=p, workspace=workspace, external_source="clickup", external_id=ext)
    return out


def send(client, ws, pairs, source="clickup"):
    return client.post(url(ws), {"external_source": source, "pairs": pairs}, format="json")


def relations():
    return {frozenset((r.issue_id, r.related_issue_id)): r for r in IssueRelation.objects.all()}


@pytest.mark.django_db
class TestRelaciones:
    def test_crea_relacionada_con_y_cruza_proyectos(self, api_key_client, workspace, tasks):
        r = send(api_key_client, workspace, [["a", "b"], ["a", "x"]])
        assert r.status_code == 200, r.data
        assert r.data == {"creadas": 2, "ya_estaban": 0, "sin_tarea": 0}
        rels = relations()
        assert set(rels) == {frozenset((tasks["a"].id, tasks["b"].id)), frozenset((tasks["a"].id, tasks["x"].id))}
        assert {r.relation_type for r in rels.values()} == {"relates_to"}

    def test_idempotente_en_ambos_sentidos(self, api_key_client, workspace, tasks):
        send(api_key_client, workspace, [["a", "b"]])
        r = send(api_key_client, workspace, [["b", "a"], ["a", "b"]])
        assert r.data == {"creadas": 0, "ya_estaban": 1, "sin_tarea": 0}
        assert IssueRelation.objects.count() == 1

    def test_respeta_relacion_existente_de_otro_tipo(self, api_key_client, workspace, project, tasks):
        IssueRelation.objects.create(issue=tasks["c"], related_issue=tasks["a"], relation_type="blocked_by",
                                     project=project, workspace=workspace)
        r = send(api_key_client, workspace, [["a", "c"]])
        assert r.data["creadas"] == 0
        assert IssueRelation.objects.get().relation_type == "blocked_by"

    def test_no_recrea_la_borrada_a_mano(self, api_key_client, workspace, tasks):
        send(api_key_client, workspace, [["a", "b"]])
        IssueRelation.objects.get().delete()  # soft delete de Plane
        r = send(api_key_client, workspace, [["a", "b"]])
        assert r.data["creadas"] == 0 and IssueRelation.objects.count() == 0

    def test_sin_tarea_y_consigo_misma(self, api_key_client, workspace, tasks):
        r = send(api_key_client, workspace, [["a", "zzz"], ["a", "a"]])
        assert r.data == {"creadas": 0, "ya_estaban": 0, "sin_tarea": 1}

    def test_solo_su_origen(self, api_key_client, workspace, tasks):
        r = send(api_key_client, workspace, [["a", "b"]], source="jira")
        assert r.data == {"creadas": 0, "ya_estaban": 0, "sin_tarea": 1}

    def test_formato_invalido(self, api_key_client, workspace, tasks):
        assert send(api_key_client, workspace, [["a"]]).status_code == 400
        assert send(api_key_client, workspace, "a,b").status_code == 400
        assert send(api_key_client, workspace, [["a", 1]]).status_code == 400
        assert send(api_key_client, workspace, [["a", "b"]], source="").status_code == 400
        assert send(api_key_client, workspace, [["a", str(i)] for i in range(MAX_PAIRS + 1)]).status_code == 400

    def test_miembro_no_admin_no_puede(self, member_factory, workspace, tasks):
        user, _ = member_factory("ana@example.com", MEMBER)
        token = APIToken.objects.create(user=user, label="ana", token="ana-token-123")
        c = APIClient()
        c.credentials(HTTP_X_API_KEY=token.token)
        assert send(c, workspace, [["a", "b"]]).status_code == 403
        assert IssueRelation.objects.count() == 0

    def test_otro_workspace_no_ve_tareas(self, api_key_client, workspace, tasks):
        from plane.db.models import Workspace, WorkspaceMember

        ws2 = Workspace.objects.create(name="Otro", owner=workspace.owner, slug="otro-ws")
        WorkspaceMember.objects.create(workspace=ws2, member=workspace.owner, role=ADMIN)
        r = send(api_key_client, ws2, [["a", "b"]])
        assert r.data == {"creadas": 0, "ya_estaban": 0, "sin_tarea": 1}
