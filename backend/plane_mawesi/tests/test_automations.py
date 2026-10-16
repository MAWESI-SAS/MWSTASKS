# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
from unittest import mock

import pytest

from plane.db.models import Issue, IssueActivity, IssueAssignee, IssueLabel, Label, Module, ModuleIssue, State

from plane_mawesi import automations as A
from plane_mawesi import recurrence as R
from plane_mawesi.models import Automation, TaskTemplate
from plane_mawesi.tests.conftest import ADMIN, MEMBER


def url(ws, project, tail=""):
    return f"/api/mawesi/workspaces/{ws.slug}/projects/{project.id}/automations/{tail}"


def activity(issue, **kw):
    return IssueActivity(issue=issue, project=issue.project, workspace=issue.workspace, epoch=0, **kw)


def rule(project, created_by=None, **kw):
    r = Automation(project=project, workspace=project.workspace, name="R", **kw)
    r.save(created_by_id=created_by.id if created_by else None)
    return r


def test_eventos_del_historial(db, issue):
    assert A.event_of(activity(issue, verb="created", field=None)) == ("created", "")
    assert A.event_of(activity(issue, verb="updated", field="priority", new_value="urgent")) == ("priority", "urgent")
    assert A.event_of(activity(issue, verb="created", field="modules", new_identifier="m1")) == ("added_to_list", "m1")
    assert A.event_of(activity(issue, verb="updated", field="state", new_identifier="s1")) == ("state", "s1")
    assert A.event_of(activity(issue, verb="updated", field="priority", new_value="urgent", comment=A.MARK)) is None
    assert A.event_of(activity(issue, verb="updated", field="description")) is None


@pytest.mark.django_db
class TestAutomations:
    def test_api_solo_admin_y_validacion(self, member_factory, workspace, project):
        _, admin = member_factory("admin@example.com", ADMIN)
        _, ana = member_factory("ana@example.com", MEMBER)
        done = State.objects.create(name="Done", group="completed", project=project, workspace=workspace)
        body = {"name": "Urgente a soporte", "trigger": "priority", "trigger_value": "urgent", "actions": {"due_in_days": 1}}
        assert ana.post(url(workspace, project), body, format="json").status_code == 403
        r = admin.post(url(workspace, project), body, format="json")
        assert r.status_code == 201 and r.json()["actions"] == {"due_in_days": 1}
        data = ana.get(url(workspace, project)).json()
        assert len(data["rules"]) == 1 and {s["name"] for s in data["states"]} >= {"Backlog", "Done"}
        rid = r.json()["id"]
        assert admin.patch(url(workspace, project, f"{rid}/"), {"enabled": False}, format="json").json()["enabled"] is False
        for bad in (
            {**body, "actions": {}},
            {**body, "trigger_value": "altísima"},
            {"name": "x", "trigger": "state", "trigger_value": str(done.id), "actions": {"state_id": str(done.id)}},
            {**body, "actions": {"assignee_ids": ["00000000-0000-0000-0000-000000000000"]}},
        ):
            assert admin.post(url(workspace, project), bad, format="json").status_code == 400
        assert admin.delete(url(workspace, project, f"{rid}/")).status_code == 204

    def test_prioridad_urgente_asigna_etiqueta_y_vence(self, member_factory, workspace, project, issue):
        ana, _ = member_factory("ana@example.com", MEMBER)
        label = Label.objects.create(name="incidente", project=project, workspace=workspace)
        rule(project, created_by=ana, trigger="priority", trigger_value="urgent",
             actions={"assignee_ids": [str(ana.id)], "label_ids": [str(label.id)], "due_in_days": 0})
        assert A.run(str(issue.id), str(project.id), "priority", "urgent") == 1
        issue.refresh_from_db()
        assert issue.target_date == R.today()
        assert IssueAssignee.objects.filter(issue=issue, assignee=ana).exists()
        assert IssueLabel.objects.filter(issue=issue, label=label).exists()
        marks = IssueActivity.objects.filter(issue=issue, comment=A.MARK)
        assert {m.field for m in marks} == {"assignees", "labels", "target_date"}
        assert all(A.event_of(m) is None for m in marks)  # no encadenan reglas
        assert A.run(str(issue.id), str(project.id), "priority", "urgent") == 1
        assert IssueAssignee.objects.filter(issue=issue, assignee=ana).count() == 1  # no duplica

    def test_condicion_de_lista_y_cambio_de_estado(self, workspace, project, issue):
        done = State.objects.create(name="Done", group="completed", project=project, workspace=workspace)
        review = State.objects.create(name="Revisión", group="started", project=project, workspace=workspace)
        incidentes = Module.objects.create(name="Soporte / Incidentes", project=project, workspace=workspace)
        rule(project, trigger="state", trigger_value=str(review.id), module=incidentes, actions={"state_id": str(done.id)})
        assert A.run(str(issue.id), str(project.id), "state", str(review.id)) == 0  # no está en la lista
        ModuleIssue.objects.create(module=incidentes, issue=issue, project=project, workspace=workspace)
        assert A.run(str(issue.id), str(project.id), "state", str(review.id)) == 1
        issue.refresh_from_db()
        assert issue.state_id == done.id and issue.completed_at is not None

    def test_entra_a_la_lista_agrega_subtareas_y_creada_no_aplica_a_subtareas(self, member_factory, workspace, project, issue):
        ana, _ = member_factory("ana@example.com", MEMBER)
        lista = Module.objects.create(name="Backlog / Workitems", project=project, workspace=workspace)
        t = TaskTemplate.objects.create(project=project, workspace=workspace, name="Fases",
                                        subtasks=[{"name": "Diseño", "priority": "none", "checklist": []}])
        rule(project, created_by=ana, trigger="added_to_list", trigger_value=str(lista.id), actions={"template_id": str(t.id)})
        rule(project, created_by=ana, trigger="created", actions={"priority": "high"})
        assert A.run(str(issue.id), str(project.id), "added_to_list", str(lista.id)) == 1
        sub = Issue.objects.get(parent=issue)
        assert sub.name == "Diseño - Tarea"
        assert A.run(str(sub.id), str(project.id), "created", "") == 0  # la subtarea no dispara "se crea"

    def test_encola_solo_si_hay_regla(self, workspace, project, issue, django_capture_on_commit_callbacks):
        with mock.patch("plane_mawesi.tasks.run_automations.delay") as delay:
            with django_capture_on_commit_callbacks(execute=True):
                activity(issue, verb="updated", field="priority", new_value="urgent").save()
            assert delay.call_count == 0
            rule(project, trigger="priority", trigger_value="urgent", actions={"priority": "high"})
            with django_capture_on_commit_callbacks(execute=True):
                activity(issue, verb="updated", field="priority", new_value="urgent").save()
                activity(issue, verb="updated", field="priority", new_value="urgent", comment=A.MARK).save()
            assert delay.call_count == 1

    def test_historial_de_plane_en_bloque(self, workspace, project, issue, django_capture_on_commit_callbacks):
        """Plane guarda el historial con bulk_create (sin post_save): se lee al terminar su tarea issue_activity."""
        rule(project, trigger="priority", trigger_value="urgent", actions={"priority": "high"})
        task = mock.Mock()
        task.name = A.ISSUE_ACTIVITY_TASK
        with mock.patch("plane_mawesi.tasks.run_automations.delay") as delay:
            with django_capture_on_commit_callbacks(execute=True):
                A.on_task_prerun(task_id="t1", task=task)
                IssueActivity.objects.bulk_create([activity(issue, verb="updated", field="priority", new_value="urgent")])
                A.on_task_postrun(task_id="t1", task=task, kwargs={"issue_id": str(issue.id)}, state="SUCCESS")
            assert delay.call_count == 1
            other = mock.Mock()
            other.name = "plane.bgtasks.otra"
            with django_capture_on_commit_callbacks(execute=True):
                A.on_task_prerun(task_id="t2", task=other)
                A.on_task_postrun(task_id="t2", task=other, kwargs={"issue_id": str(issue.id)}, state="SUCCESS")
            assert delay.call_count == 1
