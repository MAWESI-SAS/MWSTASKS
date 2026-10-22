# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime as dt

import pytest
from django.urls import resolve
from django.utils import timezone

from plane.db.models import Issue, State

from plane_mawesi.views import analytics as an


def at(y, m, d=10):
    return timezone.make_aware(dt.datetime(y, m, d, 12))


@pytest.fixture
def history(db, project):
    """Tareas migradas de ClickUp: creadas en 2025, una cerrada dos meses después. El proyecto se creó hoy."""
    done = State.objects.create(name="Done", group="completed", project=project, workspace=project.workspace)
    a = Issue.objects.create(name="A", project=project, workspace=project.workspace)
    b = Issue.objects.create(name="B", project=project, workspace=project.workspace, state=done)
    Issue.objects.filter(pk=a.pk).update(created_at=at(2025, 1))
    Issue.objects.filter(pk=b.pk).update(created_at=at(2025, 1, 20), completed_at=at(2025, 3))
    return a, b


def by_month(data):
    return {row["key"]: (row["created_issues"], row["completed_issues"]) for row in data["data"]}


@pytest.mark.django_db
class TestCreatedVsResolved:
    def test_rutas_propias_delante_de_las_de_plane(self):
        ids = "00000000-0000-0000-0000-000000000001"
        assert resolve("/api/workspaces/ws/advance-analytics-charts/").func.cls is an.WorkspaceCompletionChartEndpoint
        assert resolve(f"/api/workspaces/ws/projects/{ids}/advance-analytics-charts/").func.cls is an.ProjectCompletionChartEndpoint

    def test_workspace_desde_la_tarea_mas_vieja_y_resueltas_por_fecha_de_cierre(self, session_client, workspace, history):
        r = session_client.get(f"/api/workspaces/{workspace.slug}/advance-analytics-charts/?type=work-items")
        assert r.status_code == 200
        months = by_month(r.data)
        assert r.data["data"][0]["key"] == "2025-01-01"
        assert months["2025-01-01"] == (2, 0)
        assert months["2025-03-01"] == (0, 1)
        assert r.data["data"][-1]["key"] == timezone.now().date().replace(day=1).isoformat()

    def test_proyecto(self, session_client, workspace, project, history):
        r = session_client.get(f"/api/workspaces/{workspace.slug}/projects/{project.id}/advance-analytics-charts/?type=work-items")
        assert r.status_code == 200
        months = by_month(r.data)
        assert months["2025-01-01"] == (2, 0) and months["2025-03-01"] == (0, 1)
