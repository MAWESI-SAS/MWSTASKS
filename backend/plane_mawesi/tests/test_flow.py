# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from plane.db.models import Issue, IssueActivity, State

from plane_mawesi import flow as F
from plane_mawesi.tests.conftest import MEMBER

BOG = ZoneInfo("America/Bogota")


def at(day, hour=12):
    return dt.datetime(2026, 10, day, hour, 0, tzinfo=BOG)


def test_percentiles():
    assert F.stats([5, 1, 3, 2, 4]) == {"count": 5, "avg": 3.0, "p50": 3.0, "p85": 4.4}
    assert F.stats([]) == {"count": 0, "avg": None, "p50": None, "p85": None}


@pytest.mark.django_db
def test_flujo_acumulado_lead_y_cycle_time(workspace, project):
    backlog = State.objects.get(project=project, group="backlog")
    doing = State.objects.create(name="In Progress", group="started", project=project, workspace=workspace, sequence=2)
    done = State.objects.create(name="Done", group="completed", project=project, workspace=workspace, sequence=3)
    gone = State.objects.create(name="Cancelled", group="cancelled", project=project, workspace=workspace, sequence=4)

    # A: creada el 10, empieza el 12, termina el 15 (con historial).
    a = Issue.objects.create(name="A", project=project, workspace=workspace, state=done)
    Issue.objects.filter(pk=a.pk).update(created_at=at(10), completed_at=at(15))
    for when, old, new in [(at(12), backlog, doing), (at(15), doing, done)]:
        act = IssueActivity.objects.create(issue=a, project=project, workspace=workspace, field="state", verb="updated",
                                           old_value=old.name, new_value=new.name, old_identifier=old.id, new_identifier=new.id, epoch=0)
        IssueActivity.objects.filter(pk=act.pk).update(created_at=when)
    # B: en curso desde el 11, sin historial (estado actual desde que se creó).
    b = Issue.objects.create(name="B", project=project, workspace=workspace, state=doing)
    Issue.objects.filter(pk=b.pk).update(created_at=at(11))
    # C: terminada antes de la ventana: cuenta fija en Done.
    c = Issue.objects.create(name="C", project=project, workspace=workspace, state=done)
    Issue.objects.filter(pk=c.pk).update(created_at=at(1), completed_at=at(2))
    # D: cancelada: no se cuenta.
    Issue.objects.create(name="D", project=project, workspace=workspace, state=gone)

    out = F.analyze(project.id, 14, at(20, 18))  # ventana: 7 al 20 de octubre
    assert [s["name"] for s in out["states"]] == ["Backlog", "In Progress", "Done"]
    cfd, days = out["cfd"], out["days"]
    on = lambda state, day: cfd[str(state.id)][days.index(f"2026-10-{day:02d}")]
    assert (on(backlog, 10), on(doing, 10), on(done, 10)) == (1, 0, 1)  # A en Backlog, C terminada
    assert (on(backlog, 12), on(doing, 12), on(done, 12)) == (0, 2, 1)  # A y B en curso
    assert (on(backlog, 16), on(doing, 16), on(done, 16)) == (0, 1, 2)
    assert out["lead_time"]["count"] == 1 and out["lead_time"]["avg"] == 5.0
    assert out["cycle_time"]["avg"] == 3.0 and out["cycle_time_missing"] == 0
    assert sum(w["done"] for w in out["throughput"]) == 1
    assert [x["name"] for x in out["aging"]] == ["B"] and out["wip"] == 1


@pytest.mark.django_db
def test_endpoint_valida_ventana(member_factory, workspace, project):
    _, c = member_factory("ana@example.com", MEMBER)
    base = f"/api/mawesi/workspaces/{workspace.slug}/projects/{project.id}/flow/"
    assert c.get(base + "?days=30").status_code == 200
    assert c.get(base + "?days=7").status_code == 400
    assert c.get(base + "?days=30&module=nope").status_code == 400
