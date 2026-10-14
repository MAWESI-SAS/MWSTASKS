# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime

import pytest

from plane.db.models import IssueActivity, Project, ProjectMember

from plane_mawesi.models import Worklog
from plane_mawesi.tests.conftest import ADMIN, GUEST, MEMBER


def url(ws, project, issue, pk=None, prefix="api/mawesi"):
    base = f"/{prefix}/workspaces/{ws.slug}/projects/{project.id}/issues/{issue.id}/worklogs/"
    return f"{base}{pk}/" if pk else base


@pytest.mark.django_db
class TestCrear:
    def test_miembro_registra_y_queda_historial(self, member_factory, workspace, project, issue, today):
        user, client = member_factory("ana@example.com", MEMBER)
        r = client.post(url(workspace, project, issue), {"duration_minutes": 90, "date": today, "description": "Soporte"}, format="json")
        assert r.status_code == 201, r.data
        assert r.data["member"] == user.id and r.data["duration_minutes"] == 90
        act = IssueActivity.objects.get(issue=issue, field="worklog")
        assert act.verb == "created" and act.new_value == "90" and act.actor_id == user.id

    def test_guest_no_puede_ver_ni_registrar(self, member_factory, workspace, project, issue, today):
        _, client = member_factory("guest@cliente.com", GUEST)
        assert client.get(url(workspace, project, issue)).status_code == 403
        assert client.post(url(workspace, project, issue), {"duration_minutes": 10, "date": today}, format="json").status_code == 403

    def test_sin_membresia_no_puede(self, db, workspace, project, issue, today):
        from rest_framework.test import APIClient
        from plane_mawesi.tests.conftest import make_user
        c = APIClient()
        c.force_authenticate(user=make_user("extra@x.com"))
        assert c.post(url(workspace, project, issue), {"duration_minutes": 10, "date": today}, format="json").status_code == 403

    @pytest.mark.parametrize("minutes", [0, 24 * 60 + 1])
    def test_duracion_fuera_de_rango(self, session_client, workspace, project, issue, today, minutes):
        r = session_client.post(url(workspace, project, issue), {"duration_minutes": minutes, "date": today}, format="json")
        assert r.status_code == 400

    def test_fecha_futura(self, session_client, workspace, project, issue):
        futura = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
        r = session_client.post(url(workspace, project, issue), {"duration_minutes": 30, "date": futura}, format="json")
        assert r.status_code == 400

    def test_issue_de_otro_proyecto_da_404(self, session_client, workspace, project, create_user, today):
        otro = Project.objects.create(name="Otro", identifier="OTR", workspace=workspace)
        ProjectMember.objects.create(project=otro, workspace=workspace, member=create_user, role=ADMIN)
        from plane.db.models import Issue, State
        State.objects.create(name="B", group="backlog", default=True, project=otro, workspace=workspace)
        ajeno = Issue.objects.create(name="Ajeno", project=otro, workspace=workspace)
        r = session_client.post(url(workspace, project, ajeno), {"duration_minutes": 30, "date": today}, format="json")
        assert r.status_code == 404


@pytest.mark.django_db
class TestImputarAOtros:
    def test_miembro_no_puede_imputar_a_otro(self, member_factory, workspace, project, issue, today):
        _, client = member_factory("ana@example.com", MEMBER)
        otro, _ = member_factory("beto@example.com", MEMBER)
        r = client.post(url(workspace, project, issue), {"duration_minutes": 30, "date": today, "member": str(otro.id)}, format="json")
        assert r.status_code == 403

    def test_admin_imputa_a_miembro_del_proyecto(self, session_client, member_factory, workspace, project, issue, today):
        beto, _ = member_factory("beto@example.com", MEMBER)
        r = session_client.post(url(workspace, project, issue), {"duration_minutes": 30, "date": today, "member": str(beto.id)}, format="json")
        assert r.status_code == 201 and r.data["member"] == beto.id

    def test_admin_no_imputa_a_quien_no_es_del_proyecto(self, session_client, workspace, project, issue, today):
        from plane_mawesi.tests.conftest import make_user
        ajeno = make_user("ajeno@x.com")
        r = session_client.post(url(workspace, project, issue), {"duration_minutes": 30, "date": today, "member": str(ajeno.id)}, format="json")
        assert r.status_code == 400


@pytest.mark.django_db
class TestEditarBorrar:
    def _log(self, issue, member, minutes=60):
        return Worklog.objects.create(
            issue=issue, project=issue.project, workspace=issue.workspace, member=member,
            duration_minutes=minutes, date=datetime.date.today(), created_by=member,
        )

    def test_miembro_edita_lo_suyo(self, member_factory, workspace, project, issue):
        ana, client = member_factory("ana@example.com", MEMBER)
        wl = self._log(issue, ana)
        r = client.patch(url(workspace, project, issue, wl.id), {"duration_minutes": 45}, format="json")
        assert r.status_code == 200 and r.data["duration_minutes"] == 45
        act = IssueActivity.objects.get(issue=issue, field="worklog", verb="updated")
        assert (act.old_value, act.new_value) == ("60", "45")

    def test_miembro_no_edita_lo_ajeno(self, member_factory, workspace, project, issue):
        beto, _ = member_factory("beto@example.com", MEMBER)
        _, ana_client = member_factory("ana@example.com", MEMBER)
        wl = self._log(issue, beto)
        assert ana_client.patch(url(workspace, project, issue, wl.id), {"duration_minutes": 5}, format="json").status_code == 403
        assert ana_client.delete(url(workspace, project, issue, wl.id)).status_code == 403

    def test_admin_borra_cualquiera_y_queda_historial(self, session_client, member_factory, workspace, project, issue):
        beto, _ = member_factory("beto@example.com", MEMBER)
        wl = self._log(issue, beto)
        assert session_client.delete(url(workspace, project, issue, wl.id)).status_code == 204
        assert not Worklog.objects.filter(pk=wl.id).exists()
        act = IssueActivity.objects.get(issue=issue, field="worklog", verb="deleted")
        assert act.old_value == "60" and act.old_identifier == wl.id


@pytest.mark.django_db
class TestTotalesYReporte:
    def test_totales_por_issue(self, session_client, workspace, project, issue, create_user):
        for m in (30, 45):
            Worklog.objects.create(issue=issue, project=project, workspace=workspace, member=create_user, duration_minutes=m, date=datetime.date.today())
        r = session_client.get(f"/api/mawesi/workspaces/{workspace.slug}/projects/{project.id}/worklogs/totals/?issue_ids={issue.id}")
        assert r.status_code == 200 and r.data == {str(issue.id): 75}

    def test_reporte_filtra_fechas_y_proyectos_ajenos(self, session_client, workspace, project, issue, create_user):
        hoy = datetime.date.today()
        Worklog.objects.create(issue=issue, project=project, workspace=workspace, member=create_user, duration_minutes=60, date=hoy)
        Worklog.objects.create(issue=issue, project=project, workspace=workspace, member=create_user, duration_minutes=15, date=hoy - datetime.timedelta(days=40))
        ajeno = Project.objects.create(name="Ajeno", identifier="AJE", workspace=workspace)  # sin membresía
        from plane.db.models import Issue, State
        State.objects.create(name="B", group="backlog", default=True, project=ajeno, workspace=workspace)
        ia = Issue.objects.create(name="X", project=ajeno, workspace=workspace)
        Worklog.objects.create(issue=ia, project=ajeno, workspace=workspace, member=create_user, duration_minutes=999, date=hoy)
        desde = (hoy - datetime.timedelta(days=7)).isoformat()
        r = session_client.get(f"/api/mawesi/workspaces/{workspace.slug}/worklogs/report/?from={desde}&to={hoy.isoformat()}")
        assert r.status_code == 200
        assert r.data["total_minutes"] == 60 and r.data["count"] == 1
        assert r.data["rows"][0]["project_identifier"] == "CON"

    def test_reporte_fecha_invalida(self, session_client, workspace):
        assert session_client.get(f"/api/mawesi/workspaces/{workspace.slug}/worklogs/report/?from=13-10-2026").status_code == 400


@pytest.mark.django_db
def test_api_key_registra(api_key_client, workspace, project, issue, today):
    r = api_key_client.post(url(workspace, project, issue, prefix="api/v1/mawesi"), {"duration_minutes": 20, "date": today}, format="json")
    assert r.status_code == 201, r.data


@pytest.mark.django_db
def test_rutas_de_plane_siguen_vivas(api_client):
    assert api_client.get("/api/instances/").status_code in (200, 404)  # existe la ruta (404 si no hay instancia)
    assert api_client.get("/api/mawesi/ping/").data == {"mawesi": "ok"}
