# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime

import pytest
from django.utils import timezone

from plane.db.models import Issue, IssueComment, Project

from plane_mawesi.tests.conftest import GUEST, MEMBER


def url(ws, project, ids, prefix="/api/mawesi"):
    return f"{prefix}/workspaces/{ws.slug}/projects/{project.id}/last-comments/?issue_ids={','.join(str(i) for i in ids)}"


def comentar(issue, html, hace_min, actor=None):
    c = IssueComment.objects.create(issue=issue, project=issue.project, workspace=issue.workspace, comment_html=html, actor=actor)
    IssueComment.objects.filter(pk=c.pk).update(created_at=timezone.now() - datetime.timedelta(minutes=hace_min))
    return c


@pytest.mark.django_db
class TestLastComments:
    def test_el_mas_reciente_de_cada_tarea_y_solo_las_que_tienen(self, member_factory, workspace, project, issue):
        user, c = member_factory("ana@example.com", MEMBER)
        otra = Issue.objects.create(name="Otra", project=project, workspace=workspace)
        sin = Issue.objects.create(name="Sin comentarios", project=project, workspace=workspace)
        comentar(issue, "<p>viejo</p>", 60)
        nuevo = comentar(issue, "<p>nuevo</p>", 5, actor=user)
        comentar(otra, "<p>único</p>", 30)
        data = c.get(url(workspace, project, [issue.id, otra.id, sin.id])).json()
        assert set(data) == {str(issue.id), str(otra.id)}
        assert data[str(issue.id)]["comment_html"] == "<p>nuevo</p>"
        assert data[str(issue.id)]["id"] == str(nuevo.id) and data[str(issue.id)]["actor"] == str(user.id)
        assert data[str(otra.id)]["comment_html"] == "<p>único</p>"

    def test_no_mezcla_tareas_de_otro_proyecto(self, member_factory, workspace, project, create_user):
        _, c = member_factory("ana@example.com", MEMBER)
        ajeno = Project.objects.create(name="Ajeno", identifier="AJE", workspace=workspace, created_by=create_user)
        t = Issue.objects.create(name="Ajena", project=ajeno, workspace=workspace)
        comentar(t, "<p>no debe salir</p>", 1)
        assert c.get(url(workspace, project, [t.id])).json() == {}

    def test_sin_ids_vacio_ids_malos_400_y_guest_no(self, member_factory, workspace, project, issue):
        _, c = member_factory("ana@example.com", MEMBER)
        assert c.get(f"/api/mawesi/workspaces/{workspace.slug}/projects/{project.id}/last-comments/").json() == {}
        assert c.get(url(workspace, project, ["no-es-uuid"])).status_code == 400
        _, g = member_factory("guest@example.com", GUEST)
        assert g.get(url(workspace, project, [issue.id])).status_code == 403

    def test_api_key(self, api_key_client, workspace, project, issue):
        comentar(issue, "<p>hola</p>", 1)
        r = api_key_client.get(url(workspace, project, [issue.id], prefix="/api/v1/mawesi"))
        assert r.status_code == 200 and r.json()[str(issue.id)]["comment_html"] == "<p>hola</p>"
