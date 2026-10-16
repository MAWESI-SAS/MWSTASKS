# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from plane.db.models import Issue, IssueActivity, Module, ModuleIssue, State

from plane_mawesi import sla as S
from plane_mawesi.models import SlaPolicy
from plane_mawesi.tests.conftest import ADMIN, MEMBER

BOG = ZoneInfo("America/Bogota")
CAL = S.Calendar()


def bog(*args):
    return dt.datetime(*args, tzinfo=BOG)


def test_festivos_colombia_2026():
    expected = {(1, 1), (1, 12), (3, 23), (4, 2), (4, 3), (5, 1), (5, 18), (6, 8), (6, 15), (6, 29), (7, 20),
                (8, 7), (8, 17), (10, 12), (11, 2), (11, 16), (12, 8), (12, 25)}
    assert {(d.month, d.day) for d in S.colombia_holidays(2026)} == expected


def test_suma_horas_habiles_saltando_fin_de_semana_y_festivo():
    # Viernes 2026-03-20 17:00 + 4 h: 1 h el viernes, lunes 23 es festivo (San José), sigue martes 24 hasta 11:00.
    assert CAL.add_minutes(bog(2026, 3, 20, 17, 0), 240) == bog(2026, 3, 24, 11, 0)
    # Creado fuera de horario (sábado): arranca el lunes hábil siguiente a las 8:00.
    assert CAL.add_minutes(bog(2026, 10, 17, 22, 0), 60) == bog(2026, 10, 19, 9, 0)


def test_minutos_habiles_entre_dos_momentos():
    assert CAL.minutes_between(bog(2026, 10, 16, 17, 0), bog(2026, 10, 19, 9, 0)) == 120  # vie 17-18 + lun 8-9
    assert CAL.minutes_between(bog(2026, 10, 19, 9, 0), bog(2026, 10, 16, 17, 0)) == 0


def test_estados_del_sla():
    hours = S.DEFAULT_HOURS
    created = bog(2026, 10, 19, 8, 0)  # lunes
    run = lambda **kw: S.sla_for(created_at=created, hours=hours, cal=CAL, completed_at=None, **kw)["status"]
    assert run(priority="urgent", state_group="started", now=bog(2026, 10, 19, 9, 0)) == "on_track"
    assert run(priority="urgent", state_group="started", now=bog(2026, 10, 19, 11, 30)) == "at_risk"  # queda 30 min
    assert run(priority="urgent", state_group="started", now=bog(2026, 10, 19, 12, 1)) == "breached"
    assert run(priority="urgent", state_group="cancelled", now=bog(2026, 10, 19, 12, 1)) == "cancelled"
    done = S.sla_for(created_at=created, priority="high", hours=hours, cal=CAL, state_group="completed",
                     completed_at=bog(2026, 10, 19, 15, 0), now=bog(2026, 10, 30, 0, 0))
    assert done["status"] == "met" and done["elapsed_minutes"] == 420 and done["due_at"] == bog(2026, 10, 19, 16, 0)


def test_tiempo_en_cada_estado():
    out = S.time_in_states(created_at=bog(2026, 10, 19, 8, 0), current_state="Done", now=bog(2026, 10, 19, 12, 0), cal=CAL,
                           changes=[(bog(2026, 10, 19, 9, 0), "Todo", "In Progress"), (bog(2026, 10, 19, 11, 0), "In Progress", "Done")])
    assert [(r["state"], r["minutes"]) for r in out] == [("Todo", 60), ("In Progress", 120), ("Done", 60)]


def url(ws, project, tail=""):
    return f"/api/mawesi/workspaces/{ws.slug}/projects/{project.id}/{tail}"


@pytest.mark.django_db
class TestSlaApi:
    def test_politica_solo_admin(self, member_factory, workspace, project):
        _, admin = member_factory("admin@example.com", ADMIN)
        _, member = member_factory("ana@example.com", MEMBER)
        body = {"hours": S.DEFAULT_HOURS, "work_start": "08:00", "work_end": "18:00", "workdays": [0, 1, 2, 3, 4]}
        assert member.put(url(workspace, project, "sla/"), body, format="json").status_code == 403
        r = admin.put(url(workspace, project, "sla/"), body, format="json")
        assert r.status_code == 200 and r.json()["policy"]["hours"]["urgent"] == 4
        assert member.get(url(workspace, project, "sla/")).json()["policy"]["work_end"] == "18:00"
        bad = {**body, "hours": {**S.DEFAULT_HOURS, "low": 0}}
        assert admin.put(url(workspace, project, "sla/"), bad, format="json").status_code == 400

    def test_lote_solo_del_modulo_y_detalle_con_estados(self, member_factory, workspace, project, issue):
        _, c = member_factory("ana@example.com", MEMBER)
        mod = Module.objects.create(name="Soporte - TQ / Incidentes", project=project, workspace=workspace)
        incidente = Issue.objects.create(name="Incidente", project=project, workspace=workspace, priority="urgent")
        ModuleIssue.objects.create(module=mod, issue=incidente, project=project, workspace=workspace)
        SlaPolicy.objects.create(project=project, workspace=workspace, module=mod)
        data = c.get(url(workspace, project, f"sla/issues/?issue_ids={issue.id},{incidente.id}")).json()
        assert list(data) == [str(incidente.id)] and data[str(incidente.id)]["target_minutes"] == 240
        IssueActivity.objects.create(issue=incidente, project=project, workspace=workspace, field="state", verb="updated",
                                     old_value="Backlog", new_value="In Progress", epoch=0)
        detail = c.get(url(workspace, project, f"issues/{incidente.id}/sla/")).json()
        assert detail["sla"]["status"] in ("on_track", "at_risk", "breached")
        assert [s["state"] for s in detail["states"]] == ["Backlog", "In Progress"]
        other = c.get(url(workspace, project, f"issues/{issue.id}/sla/")).json()
        assert other["sla"] is None

    def test_sin_politica_no_hay_sla(self, member_factory, workspace, project, issue):
        _, c = member_factory("ana@example.com", MEMBER)
        assert c.get(url(workspace, project, f"sla/issues/?issue_ids={issue.id}")).json() == {}
