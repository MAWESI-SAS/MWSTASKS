# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime as dt

import pytest

from plane.db.models import Issue, IssueActivity, IssueRelation, State

from plane_mawesi import dependencies as D
from plane_mawesi.models import DependencyPolicy
from plane_mawesi.tests.conftest import ADMIN, MEMBER


@pytest.fixture
def states(db, project):
    ws = project.workspace
    mk = lambda name, group, seq: State.objects.create(name=name, group=group, project=project, workspace=ws, sequence=seq)
    return {
        "backlog": State.objects.get(project=project, group="backlog"),
        "todo": mk("Todo", "unstarted", 2), "doing": mk("In Progress", "started", 3), "blocked": mk("Blocked", "started", 4),
        "done": mk("Done", "completed", 5), "cancelled": mk("Cancelled", "cancelled", 6),
    }


def task(project, name, state, start=None, due=None):
    return Issue.objects.create(name=name, project=project, workspace=project.workspace, state=state,
                                start_date=start, target_date=due)


def depends(dependent, predecessor, kind=D.FS):
    """`dependent` espera a `predecessor` (guardado como lo guarda Plane)."""
    a, b = (dependent, predecessor) if kind == D.FS else (predecessor, dependent)
    return IssueRelation.objects.create(issue=a, related_issue=b, relation_type=kind, project=a.project, workspace=a.workspace)


def url(ws, project, tail):
    return f"/api/workspaces/{ws.slug}/projects/{project.id}/{tail}"


@pytest.mark.django_db
class TestReglas:
    def test_tipos_fs_ss_ff(self, project, states):
        a = task(project, "A", states["todo"])
        b = task(project, "B", states["todo"])
        depends(b, a, D.FS)
        assert [x["key"] for x in D.blockers(b, "started")] == [f"CON-{a.sequence_id}"]
        a.state = states["cancelled"]; a.save()
        assert D.blockers(b, "started") == []  # cancelada cuenta como resuelta

        c, d = task(project, "C", states["todo"]), task(project, "D", states["todo"])
        depends(d, c, D.SS)
        assert len(D.blockers(d, "started")) == 1
        c.state = states["doing"]; c.save()
        assert D.blockers(d, "started") == []

        e, f = task(project, "E", states["doing"]), task(project, "F", states["doing"])
        depends(f, e, D.FF)
        assert D.blockers(f, "started") == [] and len(D.blockers(f, "completed")) == 1

    def test_ciclos(self, project, states, workspace):
        a, b, c = (task(project, n, states["todo"]) for n in "ABC")
        depends(b, a)
        depends(c, b, D.SS)
        assert D.would_cycle(workspace.id, c.id, a.id)  # a esperaría a c, que espera a b, que espera a a
        assert not D.would_cycle(workspace.id, a.id, c.id)
        assert D.would_cycle(workspace.id, a.id, a.id)

    def test_corrimiento_flexible_mira_todos_los_predecesores(self, project, states):
        d = dt.date
        a = task(project, "A", states["doing"], d(2026, 11, 2), d(2026, 11, 6))
        b = task(project, "B", states["doing"], d(2026, 11, 2), d(2026, 11, 10))
        c = task(project, "C", states["todo"], d(2026, 11, 5), d(2026, 11, 9))
        depends(c, a)
        depends(c, b)
        # B termina el 10: C (5 al 9) tiene que empezar el 10 → se corre 5 días y conserva su duración.
        assert D.shift_needed(c, [(a, D.FS), (b, D.FS)]) == 5
        assert D.reschedule(b.id, None) == 1
        c.refresh_from_db()
        assert (c.start_date, c.target_date) == (d(2026, 11, 10), d(2026, 11, 14))
        # Ya no choca: no se mueve más, y nunca se adelanta.
        assert D.reschedule(b.id, None) == 0
        Issue.objects.filter(pk=b.pk).update(target_date=d(2026, 11, 3))
        assert D.reschedule(b.id, None) == 0

    def test_corrimiento_apagado(self, project, states):
        DependencyPolicy.objects.create(project=project, workspace=project.workspace, reschedule=False)
        a = task(project, "A", states["doing"], None, dt.date(2026, 11, 20))
        b = task(project, "B", states["todo"], dt.date(2026, 11, 1), dt.date(2026, 11, 2))
        depends(b, a)
        assert D.reschedule(a.id, None) == 0

    def test_desbloqueo_saca_de_blocked(self, project, states, create_user):
        a = task(project, "A", states["doing"])
        b = task(project, "B", states["blocked"])
        c = task(project, "C", states["doing"])
        depends(b, a)
        depends(b, c)
        a.state = states["done"]; a.save()
        assert D.unblock(a.id, create_user.id) == 0  # todavía espera a C
        c.state = states["done"]; c.save()
        assert D.unblock(c.id, create_user.id) == 1
        b.refresh_from_db()
        assert b.state_id == states["todo"].id
        assert IssueActivity.objects.filter(issue=b, field=D.FIELD, verb="unblocked").count() == 1


@pytest.mark.django_db
class TestApi:
    def test_no_deja_empezar_ni_terminar_bloqueada(self, member_factory, workspace, project, states):
        _, c = member_factory("ana@example.com", MEMBER)
        a = task(project, "Diseño", states["doing"])
        b = task(project, "Desarrollo", states["todo"])
        depends(b, a)
        r = c.patch(url(workspace, project, f"issues/{b.id}/"), {"state_id": str(states["doing"].id)}, format="json")
        assert r.status_code == 409 and r.json()["mawesi"] == "dependency_blocked" and "Diseño" in r.json()["error"]
        b.refresh_from_db()
        assert b.state_id == states["todo"].id
        # Volver atrás o cancelar sí se puede; otros campos también.
        assert c.patch(url(workspace, project, f"issues/{b.id}/"), {"state_id": str(states["backlog"].id)}, format="json").status_code in (200, 204)
        assert c.patch(url(workspace, project, f"issues/{b.id}/"), {"priority": "high"}, format="json").status_code in (200, 204)
        # Con la política apagada pasa.
        DependencyPolicy.objects.create(project=project, workspace=workspace, enforce=False)
        assert c.patch(url(workspace, project, f"issues/{b.id}/"), {"state_id": str(states["doing"].id)}, format="json").status_code in (200, 204)

    def test_api_key(self, api_key_client, workspace, project, states, member_factory):
        a = task(project, "A", states["doing"])
        b = task(project, "B", states["todo"])
        depends(b, a)
        # El dueño del token es admin del workspace (fixture de Plane): integración, no se frena.
        r = api_key_client.patch(f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-items/{b.id}/",
                                 {"state": str(states["doing"].id)}, format="json")
        assert r.status_code == 200

    def test_api_key_de_miembro_se_frena(self, workspace, project, states, member_factory):
        from rest_framework.test import APIClient

        from plane.db.models import APIToken

        u, _ = member_factory("empleado.ai@example.com", MEMBER)
        token = APIToken.objects.create(user=u, workspace=workspace, label="MAWESI AI", user_type=0)
        cli = APIClient()
        cli.credentials(HTTP_X_API_KEY=token.token)
        a = task(project, "A", states["doing"])
        b = task(project, "B", states["todo"])
        depends(b, a)
        r = cli.patch(f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/issues/{b.id}/",
                      {"state": str(states["done"].id)}, format="json")
        assert r.status_code == 409

    def test_relacion_que_cierra_un_circulo(self, member_factory, workspace, project, states):
        _, c = member_factory("ana@example.com", ADMIN)
        a = task(project, "A", states["todo"])
        b = task(project, "B", states["todo"])
        depends(b, a)
        r = c.post(url(workspace, project, f"issues/{b.id}/issue-relation/"), {"relation_type": "blocking", "issues": [str(a.id)]}, format="json")
        assert r.status_code == 400 and r.json()["mawesi"] == "dependency_cycle"
        r = c.post(url(workspace, project, f"issues/{a.id}/issue-relation/"), {"relation_type": "relates_to", "issues": [str(b.id)]}, format="json")
        assert r.status_code == 201

    def test_estado_para_las_tarjetas(self, member_factory, workspace, project, states):
        _, c = member_factory("ana@example.com", MEMBER)
        a = task(project, "A", states["doing"], dt.date(2026, 11, 2), dt.date(2026, 11, 9))
        b = task(project, "B", states["todo"], dt.date(2026, 11, 5), dt.date(2026, 11, 6))
        libre = task(project, "Libre", states["todo"])
        depends(b, a)
        data = c.get(f"/api/mawesi/workspaces/{workspace.slug}/projects/{project.id}/dependencies/?issue_ids={a.id},{b.id},{libre.id}").json()
        assert list(data) == [str(b.id)]
        assert data[str(b.id)]["conflict"] and data[str(b.id)]["blocked_by"][0]["name"] == "A"

    def test_lote_de_dependencias_desde_clickup(self, api_key_client, workspace, project, states):
        a = task(project, "053", states["todo"])
        b = task(project, "055", states["todo"])
        Issue.objects.filter(pk=a.pk).update(external_source="clickup", external_id="053")
        Issue.objects.filter(pk=b.pk).update(external_source="clickup", external_id="055")
        IssueRelation.objects.create(issue=a, related_issue=b, relation_type="relates_to", project=project, workspace=workspace)
        r = api_key_client.post(f"/api/v1/mawesi/workspaces/{workspace.slug}/relations/",
                                {"external_source": "clickup", "relation_type": "blocked_by", "pairs": [["055", "053"]]},
                                format="json").json()
        assert r["convertidas"] == 1 and r["creadas"] == 0
        rel = IssueRelation.objects.get()
        assert (rel.issue_id, rel.related_issue_id, rel.relation_type) == (b.id, a.id, "blocked_by")  # 055 espera a 053
