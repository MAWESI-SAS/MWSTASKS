# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime as dt

import pytest

from plane.db.models import Issue, IssueAssignee, IssueLabel, Label, Module, ModuleIssue, State

from plane_mawesi import recurrence as R
from plane_mawesi.models import Property, PropertyValue, Recurrence
from plane_mawesi.tests.conftest import GUEST, MEMBER

D = dt.date


def test_pasos():
    assert R.step(D(2026, 1, 31), "monthly", 1) == D(2026, 2, 28)
    assert R.step(D(2026, 10, 16), "weekdays", 1) == D(2026, 10, 19)  # viernes → lunes
    assert R.step(D(2026, 10, 16), "weekly", 2) == D(2026, 10, 30)
    assert R.step(D(2026, 10, 16), "daily", 3) == D(2026, 10, 19)


def test_fechas_siguientes_saltan_lo_vencido_y_mantienen_la_duracion():
    rule = Recurrence(frequency="weekly", interval=1)
    issue = Issue(start_date=D(2026, 10, 1), target_date=D(2026, 10, 2))
    # Completada tarde (hoy 20/10): la siguiente no queda en el pasado
    assert R.next_dates(rule, issue, now_date=D(2026, 10, 20)) == (D(2026, 10, 22), D(2026, 10, 23))
    assert R.next_dates(rule, Issue(), now_date=D(2026, 10, 20)) == (None, D(2026, 10, 27))


def url(ws, project, issue):
    return f"/api/mawesi/workspaces/{ws.slug}/projects/{project.id}/issues/{issue.id}/recurrence/"


@pytest.mark.django_db
class TestRecurrence:
    def test_api(self, member_factory, workspace, project, issue):
        _, ana = member_factory("ana@example.com", MEMBER)
        _, guest = member_factory("guest@example.com", GUEST)
        assert guest.get(url(workspace, project, issue)).status_code == 403
        assert ana.get(url(workspace, project, issue)).json() == {"recurrence": None}
        bad = ana.put(url(workspace, project, issue), {"frequency": "weekly", "trigger": "schedule"}, format="json")
        assert bad.status_code == 400  # sin vencimiento no se puede repetir "en la fecha"
        assert ana.put(url(workspace, project, issue), {"frequency": "yearly"}, format="json").status_code == 400
        r = ana.put(url(workspace, project, issue), {"frequency": "weekly", "interval": 2}, format="json")
        assert r.status_code == 200 and r.json()["recurrence"]["trigger"] == "complete" and r.json()["recurrence"]["next_target"]
        r = ana.put(url(workspace, project, issue), {"frequency": "monthly", "interval": 1}, format="json")
        assert r.json()["recurrence"]["frequency"] == "monthly" and Recurrence.objects.count() == 1
        assert ana.delete(url(workspace, project, issue)).status_code == 204
        assert ana.get(url(workspace, project, issue)).json() == {"recurrence": None}

    def test_al_completarla_crea_la_siguiente_copiando_todo(self, member_factory, workspace, project):
        ana, _ = member_factory("ana@example.com", MEMBER)
        done = State.objects.create(name="Done", group="completed", project=project, workspace=workspace)
        lista = Module.objects.create(name="Reuniones / Semanales", project=project, workspace=workspace)
        label = Label.objects.create(name="cliente", project=project, workspace=workspace)
        prop = Property.objects.create(name="Cliente", type="text", project=project, workspace=workspace)
        issue = Issue.objects.create(name="Reunión de seguimiento", project=project, workspace=workspace, priority="high",
                                     target_date=D(2026, 10, 16), parent=None,
                                     description_html='<ul data-type="taskList"><li data-checked="true" data-type="taskItem"><p>Acta</p></li></ul>')
        IssueAssignee.objects.create(issue=issue, assignee=ana, project=project, workspace=workspace)
        IssueLabel.objects.create(issue=issue, label=label, project=project, workspace=workspace)
        ModuleIssue.objects.create(issue=issue, module=lista, project=project, workspace=workspace)
        PropertyValue.objects.create(issue=issue, property=prop, value="TQ", project=project, workspace=workspace)
        rule = Recurrence(issue=issue, frequency="weekly", project=project, workspace=workspace)
        rule.save(created_by_id=ana.id)  # como en la API: el autor es quien la configuró

        assert R.run_due(now_date=D(2026, 10, 16)) == 0  # todavía abierta
        issue.state = done
        issue.save()
        assert R.run_due(now_date=D(2026, 10, 16)) == 1
        rule.refresh_from_db()
        new = rule.issue
        assert new.pk != issue.pk and rule.occurrences == 1 and new.name == "Reunión de seguimiento"
        assert new.target_date == D(2026, 10, 23) and new.priority == "high" and new.state.group == "backlog"
        assert 'data-checked="false"' in new.description_html and new.created_by_id == ana.id
        assert list(IssueAssignee.objects.filter(issue=new).values_list("assignee_id", flat=True)) == [ana.id]
        assert IssueLabel.objects.filter(issue=new, label=label).exists()
        assert ModuleIssue.objects.filter(issue=new, module=lista).exists()
        assert PropertyValue.objects.get(issue=new, property=prop).value == "TQ"
        assert R.run_due(now_date=D(2026, 10, 16)) == 0  # la nueva no está completa: no se duplica

    def test_en_la_fecha_aunque_no_este_completa(self, workspace, project):
        issue = Issue.objects.create(name="Backup mensual", project=project, workspace=workspace, target_date=D(2026, 10, 31))
        rule = Recurrence.objects.create(issue=issue, frequency="monthly", trigger="schedule", project=project, workspace=workspace)
        assert R.run_due(now_date=D(2026, 10, 30)) == 0
        assert R.run_due(now_date=D(2026, 10, 31)) == 1
        rule.refresh_from_db()
        assert rule.issue.target_date == D(2026, 11, 30) and rule.issue.created_by_id is None
        assert Issue.objects.filter(name="Backup mensual").count() == 2
        assert R.run_due(now_date=D(2026, 10, 31)) == 0
