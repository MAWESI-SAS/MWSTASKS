# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime

import pytest
from django.utils import timezone

from plane.db.models import Issue, IssueActivity

from plane_mawesi.models import Timer, Worklog
from plane_mawesi.tests.conftest import GUEST, MEMBER


def start_url(ws, project, issue):
    return f"/api/mawesi/workspaces/{ws.slug}/projects/{project.id}/issues/{issue.id}/timer/start/"


def back_in_time(minutes):
    Timer.objects.update(started_at=timezone.now() - datetime.timedelta(minutes=minutes))


@pytest.mark.django_db
class TestCronometro:
    def test_arrancar_parar_guarda_horas(self, member_factory, workspace, project, issue):
        user, c = member_factory("ana@example.com", MEMBER)
        r = c.post(start_url(workspace, project, issue), {"description": "Soporte"}, format="json")
        assert r.status_code == 201 and r.data["timer"]["issue_id"] == str(issue.id)
        assert c.get(f"/api/mawesi/workspaces/{workspace.slug}/timer/").data["timer"]["project_identifier"] == "CON"
        back_in_time(90)
        r = c.post(f"/api/mawesi/workspaces/{workspace.slug}/timer/stop/", {}, format="json")
        assert r.status_code == 200
        w = Worklog.objects.get(issue=issue)
        assert (w.member_id, w.duration_minutes, w.description) == (user.id, 90, "Soporte")
        assert IssueActivity.objects.filter(issue=issue, field="worklog", verb="created").count() == 1
        assert not Timer.objects.exists()
        assert c.get(f"/api/mawesi/workspaces/{workspace.slug}/timer/").data["timer"] is None

    def test_arrancar_otro_para_el_anterior(self, member_factory, workspace, project, issue):
        _, c = member_factory("ana@example.com", MEMBER)
        otra = Issue.objects.create(name="Otra", project=project, workspace=workspace)
        c.post(start_url(workspace, project, issue), {}, format="json")
        back_in_time(10)
        r = c.post(start_url(workspace, project, otra), {}, format="json")
        assert r.status_code == 201 and len(r.data["stopped"]) == 1
        assert Worklog.objects.get().issue_id == issue.id
        assert Timer.objects.get().issue_id == otra.id
        # Repetir el ▶ en la misma tarea no reinicia el cronómetro
        assert c.post(start_url(workspace, project, otra), {}, format="json").status_code == 200
        assert Timer.objects.count() == 1

    def test_mas_de_24h_se_parte(self, member_factory, workspace, project, issue):
        _, c = member_factory("ana@example.com", MEMBER)
        c.post(start_url(workspace, project, issue), {}, format="json")
        back_in_time(30 * 60)
        c.post(f"/api/mawesi/workspaces/{workspace.slug}/timer/stop/", {}, format="json")
        assert sorted(Worklog.objects.values_list("duration_minutes", flat=True)) == [360, 1440]

    def test_descartar_no_guarda(self, member_factory, workspace, project, issue):
        _, c = member_factory("ana@example.com", MEMBER)
        c.post(start_url(workspace, project, issue), {}, format="json")
        assert c.delete(f"/api/mawesi/workspaces/{workspace.slug}/timer/").status_code == 204
        assert not Timer.objects.exists() and not Worklog.objects.exists()

    def test_cada_persona_tiene_el_suyo(self, member_factory, workspace, project, issue):
        _, ana = member_factory("ana@example.com", MEMBER)
        _, beto = member_factory("beto@example.com", MEMBER)
        ana.post(start_url(workspace, project, issue), {}, format="json")
        assert beto.get(f"/api/mawesi/workspaces/{workspace.slug}/timer/").data["timer"] is None
        assert beto.post(f"/api/mawesi/workspaces/{workspace.slug}/timer/stop/", {}, format="json").status_code == 404
        assert Timer.objects.count() == 1

    def test_guest_no_puede(self, member_factory, workspace, project, issue):
        _, c = member_factory("guest@cliente.com", GUEST)
        assert c.post(start_url(workspace, project, issue), {}, format="json").status_code == 403

    def test_un_cronometro_borrado_en_blando_no_bloquea(self, member_factory, workspace, project, issue):
        # Plane borra "en blando" con queryset.delete(): esa fila no debe impedir arrancar otro.
        _, c = member_factory("ana@example.com", MEMBER)
        c.post(start_url(workspace, project, issue), {}, format="json")
        Timer.objects.all().delete()
        assert Timer.all_objects.filter(deleted_at__isnull=False).count() == 1
        r = c.post(start_url(workspace, project, issue), {}, format="json")
        assert r.status_code == 201 and r.data["timer"] is not None
