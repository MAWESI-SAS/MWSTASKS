# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from plane.db.models import IssueActivity, State

from plane_mawesi import estimates as E
from plane_mawesi.models import IssueEstimate, Worklog
from plane_mawesi.tests.conftest import GUEST, MEMBER


def url(ws, project, issue=None, tail="estimate/"):
    base = f"/api/mawesi/workspaces/{ws.slug}/projects/{project.id}/"
    return base + (f"issues/{issue.id}/{tail}" if issue else tail)


def test_restante_automatico_manual_y_cerrado():
    est = IssueEstimate(original_minutes=600)
    assert E.row(est, 360, "started")["remaining_minutes"] == 240
    assert E.row(est, 700, "started")["remaining_minutes"] == 0  # nunca negativo
    est.remaining_minutes = 300
    manual = E.row(est, 360, "started")
    assert manual["remaining_minutes"] == 300 and manual["remaining_is_manual"]
    assert E.row(est, 360, "completed")["remaining_minutes"] == 0
    assert E.row(None, 120, "started") == {"original_minutes": None, "remaining_minutes": None, "remaining_is_manual": False,
                                           "completed_minutes": 120}


@pytest.mark.django_db
class TestEstimateApi:
    def test_estimar_registrar_horas_y_corregir_restante(self, member_factory, workspace, project, issue, today):
        user, c = member_factory("ana@example.com", MEMBER)
        r = c.put(url(workspace, project, issue), {"original_minutes": 600}, format="json")
        assert r.status_code == 200 and r.json()["remaining_minutes"] == 600
        Worklog.objects.create(issue=issue, project=project, workspace=workspace, member=user, duration_minutes=90, date=today)
        assert c.get(url(workspace, project, issue)).json()["remaining_minutes"] == 510
        r = c.put(url(workspace, project, issue), {"remaining_minutes": 120}, format="json").json()
        assert (r["original_minutes"], r["remaining_minutes"], r["remaining_is_manual"], r["completed_minutes"]) == (600, 120, True, 90)
        r = c.put(url(workspace, project, issue), {"remaining_minutes": None}, format="json").json()
        assert r["remaining_minutes"] == 510 and not r["remaining_is_manual"]
        act = IssueActivity.objects.get(issue=issue, field=E.ACTIVITY_FIELD)
        assert (act.old_value, act.new_value) == (None, "600")

    def test_lote_solo_las_estimadas_y_cerrada_en_cero(self, member_factory, workspace, project, issue):
        _, c = member_factory("ana@example.com", MEMBER)
        from plane.db.models import Issue

        otra = Issue.objects.create(name="Sin estimar", project=project, workspace=workspace)
        c.put(url(workspace, project, issue), {"original_minutes": 60}, format="json")
        data = c.get(url(workspace, project, tail=f"estimates/?issue_ids={issue.id},{otra.id}")).json()
        assert list(data) == [str(issue.id)]
        done = State.objects.create(name="Done", group="completed", project=project, workspace=workspace)
        issue.state = done
        issue.save()
        assert c.get(url(workspace, project, tail=f"estimates/?issue_ids={issue.id}")).json()[str(issue.id)]["remaining_minutes"] == 0

    def test_valida_y_guest_no_puede(self, member_factory, workspace, project, issue):
        _, c = member_factory("ana@example.com", MEMBER)
        assert c.put(url(workspace, project, issue), {"original_minutes": -5}, format="json").status_code == 400
        assert c.put(url(workspace, project, issue), {}, format="json").status_code == 400
        _, g = member_factory("guest@example.com", GUEST)
        assert g.put(url(workspace, project, issue), {"original_minutes": 60}, format="json").status_code == 403

    def test_api_key_para_empleados_ai(self, api_key_client, workspace, project, issue):
        r = api_key_client.put(f"/api/v1/mawesi/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/estimate/",
                               {"original_minutes": 240}, format="json")
        assert r.status_code == 200 and r.json()["original_minutes"] == 240


@pytest.mark.django_db
def test_copia_el_campo_estimado_de_clickup(workspace, project, issue):
    import io

    from django.core.management import call_command

    from plane.db.models import Issue
    from plane_mawesi.models import Property, PropertyValue

    prop = Property.objects.create(project=project, workspace=workspace, name="Estimado (h)", type="number")
    otra = Issue.objects.create(name="Ya estimada", project=project, workspace=workspace)
    cero = Issue.objects.create(name="Cero", project=project, workspace=workspace)
    for i, v in ((issue, 1.5), (otra, 8), (cero, 0)):
        PropertyValue.objects.create(project=project, workspace=workspace, issue=i, property=prop, value=v)
    IssueEstimate.objects.create(issue=otra, project=project, workspace=workspace, original_minutes=60)
    out = io.StringIO()
    call_command("mawesi_import_estimates", "--workspace", workspace.slug, stdout=out)
    assert "1 estimados copiados, 2 saltados" in out.getvalue()
    assert IssueEstimate.objects.get(issue=issue).original_minutes == 90
    assert IssueEstimate.objects.get(issue=otra).original_minutes == 60  # lo cargado en MWSTASKS no se pisa
    call_command("mawesi_import_estimates", "--workspace", workspace.slug, stdout=io.StringIO())
    assert IssueEstimate.objects.count() == 2
