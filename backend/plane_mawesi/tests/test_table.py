# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime

import pytest

from plane.db.models import Issue, IssueAssignee, Module, ModuleIssue, State

from plane_mawesi.models import Property, PropertyOption, PropertyValue, Worklog
from plane_mawesi.tests.conftest import GUEST, MEMBER


def url(ws, project, **q):
    query = "&".join(f"{k}={v}" for k, v in q.items())
    return f"/api/mawesi/workspaces/{ws.slug}/projects/{project.id}/table/{'?' + query if query else ''}"


@pytest.mark.django_db
class TestTabla:
    def test_filas_con_horas_campos_responsables_y_modulo(self, member_factory, workspace, project, issue):
        user, c = member_factory("ana@example.com", MEMBER)
        done = State.objects.create(name="Hecho", group="completed", project=project, workspace=workspace)
        cerrada = Issue.objects.create(name="Cerrada", project=project, workspace=workspace, state=done)
        IssueAssignee.objects.create(issue=issue, assignee=user, project=project, workspace=workspace)
        mod = Module.objects.create(name="Backlog - TQ / Mejoras", project=project, workspace=workspace)
        ModuleIssue.objects.create(module=mod, issue=issue, project=project, workspace=workspace)
        Worklog.objects.create(issue=issue, project=project, workspace=workspace, member=user, duration_minutes=45,
                               date=datetime.date.today())
        prop = Property.objects.create(name="Tipo", type="select", project=project, workspace=workspace)
        opt = PropertyOption.objects.create(property=prop, name="Bug", project=project, workspace=workspace)
        PropertyValue.objects.create(issue=issue, property=prop, value=str(opt.id), project=project, workspace=workspace)

        data = c.get(url(workspace, project)).json()
        assert [r["name"] for r in data["rows"]] == ["Tarea"]  # sin cerradas por defecto
        row = data["rows"][0]
        assert row["minutes"] == 45 and row["assignee_ids"] == [str(user.id)] and row["module_ids"] == [str(mod.id)]
        assert row["values"] == {str(prop.id): str(opt.id)}
        assert data["properties"][0]["options"][0]["name"] == "Bug"
        assert data["states"][row["state_id"]]["group"] == "backlog"

        assert {r["name"] for r in c.get(url(workspace, project, closed=1)).json()["rows"]} == {"Tarea", "Cerrada"}
        assert [r["id"] for r in c.get(url(workspace, project, module=mod.id)).json()["rows"]] == [str(issue.id)]
        assert cerrada.id  # usada arriba

    def test_modulo_invalido_y_guest(self, member_factory, workspace, project):
        _, c = member_factory("ana@example.com", MEMBER)
        assert c.get(url(workspace, project, module="x")).status_code == 400
        _, g = member_factory("guest@cliente.com", GUEST)
        assert g.get(url(workspace, project)).status_code == 403
