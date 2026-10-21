# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from plane.db.models import Cycle, CycleIssue, Issue, IssueAssignee, State

from plane_mawesi import capacity as C
from plane_mawesi.models import IssueEstimate
from plane_mawesi.tests.conftest import ADMIN, MEMBER

BOG = ZoneInfo("America/Bogota")


def url(ws, project, tail):
    return f"/api/mawesi/workspaces/{ws.slug}/projects/{project.id}/{tail}"


@pytest.fixture
def cycle(db, project, create_user):
    # Lunes 19 a viernes 30 de octubre de 2026: 10 días hábiles (sin festivos).
    return Cycle.objects.create(
        name="Sprint 1", project=project, workspace=project.workspace, owned_by=create_user, timezone="America/Bogota",
        start_date=dt.datetime(2026, 10, 19, 0, 0, tzinfo=BOG), end_date=dt.datetime(2026, 10, 30, 23, 59, tzinfo=BOG),
    )


def add(cycle, name, minutes=None, assignees=(), group="started"):
    project = cycle.project
    state = State.objects.filter(project=project, group=group).first() or State.objects.create(
        name=group.title(), group=group, project=project, workspace=project.workspace)
    issue = Issue.objects.create(name=name, project=project, workspace=project.workspace, state=state)
    CycleIssue.objects.create(cycle=cycle, issue=issue, project=project, workspace=project.workspace)
    if minutes is not None:
        IssueEstimate.objects.create(issue=issue, project=project, workspace=project.workspace, original_minutes=minutes)
    for u in assignees:
        IssueAssignee.objects.create(issue=issue, assignee=u, project=project, workspace=project.workspace)
    return issue


@pytest.mark.django_db
class TestCapacity:
    def test_capacidad_contra_trabajo_restante(self, member_factory, workspace, project, cycle):
        ana, admin = member_factory("ana@example.com", ADMIN)
        beto, _ = member_factory("beto@example.com", MEMBER)
        add(cycle, "Solo Ana", 600, [ana])
        add(cycle, "Compartida", 240, [ana, beto])  # 2 h a cada uno
        add(cycle, "Sin estimar", None, [beto])
        add(cycle, "Sin responsable", 60)
        add(cycle, "Terminada", 999, [ana], group="completed")
        body = {"team_days_off": ["2026-10-23"], "members": [
            {"member_id": str(ana.id), "hours_per_day": 6, "days_off": ["2026-10-29"]},
            {"member_id": str(beto.id), "hours_per_day": "4.5"},
        ]}
        r = admin.put(url(workspace, project, f"cycles/{cycle.id}/capacity/"), body, format="json")
        assert r.status_code == 200, r.json()
        rep = C.report(cycle, dt.date(2026, 10, 26))  # lunes de la 2.ª semana: quedan 5 días hábiles
        rows = {m["display_name"]: m for m in rep["members"]}
        a, b = rows["ana"], rows["beto"]
        assert (a["days_total"], a["days_left"], a["capacity_left_minutes"]) == (8, 4, 4 * 6 * 60)
        assert (b["days_total"], b["days_left"], b["capacity_left_minutes"]) == (9, 5, 5 * 270)
        assert (a["remaining_minutes"], a["open_items"]) == (600 + 120, 2)
        assert (b["remaining_minutes"], b["unestimated"], b["open_items"]) == (120, 1, 2)
        assert rep["unassigned"] == {"remaining_minutes": 60, "unestimated": 0, "count": 1}
        assert rep["totals"]["remaining_minutes"] == 600 + 240 + 60 and rep["totals"]["open_items"] == 4

    def test_miembro_solo_cambia_lo_suyo(self, member_factory, workspace, project, cycle):
        ana, c = member_factory("ana@example.com", MEMBER)
        beto, _ = member_factory("beto@example.com", MEMBER)
        mine = {"members": [{"member_id": str(ana.id), "hours_per_day": 5}]}
        assert c.put(url(workspace, project, f"cycles/{cycle.id}/capacity/"), mine, format="json").status_code == 200
        other = {"members": [{"member_id": str(beto.id), "hours_per_day": 5}]}
        assert c.put(url(workspace, project, f"cycles/{cycle.id}/capacity/"), other, format="json").status_code == 403
        assert c.put(url(workspace, project, f"cycles/{cycle.id}/capacity/"), {"team_days_off": []}, format="json").status_code == 403
        bad = {"members": [{"member_id": str(ana.id), "hours_per_day": 30}]}
        assert c.put(url(workspace, project, f"cycles/{cycle.id}/capacity/"), bad, format="json").status_code == 400

    def test_lista_de_ciclos_y_ciclo_sin_fechas(self, member_factory, workspace, project, cycle, create_user):
        _, c = member_factory("ana@example.com", MEMBER)
        sin = Cycle.objects.create(name="Sin fechas", project=project, workspace=workspace, owned_by=create_user)
        data = c.get(url(workspace, project, "capacity/cycles/")).json()
        assert [x["name"] for x in data["cycles"]] == ["Sprint 1"] and data["current_id"] == str(cycle.id)
        assert c.get(url(workspace, project, f"cycles/{sin.id}/capacity/")).status_code == 400


@pytest.mark.django_db
def test_fechas_en_la_zona_del_proyecto(project, create_user):
    """Así guarda Plane un ciclo del 13 al 27 de octubre en un proyecto de Bogotá (cycle.timezone queda en UTC)."""
    utc = dt.timezone.utc
    project.timezone = "America/Bogota"
    project.save()
    c = Cycle.objects.create(name="Sprint 27", project=project, workspace=project.workspace, owned_by=create_user, timezone="UTC",
                             start_date=dt.datetime(2026, 10, 13, 5, 0, 1, tzinfo=utc), end_date=dt.datetime(2026, 10, 28, 4, 59, tzinfo=utc))
    assert C.cycle_dates(c) == (dt.date(2026, 10, 13), dt.date(2026, 10, 27))
