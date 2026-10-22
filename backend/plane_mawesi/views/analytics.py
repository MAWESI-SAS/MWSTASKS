# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Gráfico "Created vs Resolved" de Analytics (workspace y proyecto), con dos arreglos sobre el de Plane:

- Empieza en el mes de la tarea más vieja, no en el mes en que se creó el workspace o el proyecto en MWSTASKS
  (con lo migrado de ClickUp, Plane mostraba solo octubre de 2026 y escondía 5 años de historia).
- "Resolved" cuenta las tareas terminadas EN ese mes (completed_at), como Jira; Plane contaba las creadas ese mes que
  hoy están terminadas.

Misma respuesta que Plane ({"data": [{key, name, count, created_issues, completed_issues}], "schema"}). Las vistas de
un ciclo o de una lista (por día) siguen siendo las de Plane. Se montan en urls.py antes que las de Plane.
"""
import datetime as dt

from django.db.models import Count, Min
from django.db.models.functions import TruncMonth
from django.utils import timezone

from plane.app.views.analytic.advance import AdvanceAnalyticsChartEndpoint
from plane.app.views.analytic.project_analytics import ProjectAdvanceAnalyticsChartEndpoint
from plane.db.models import Issue, Project, Workspace


def _month(d) -> dt.date:
    return d.replace(day=1)


def monthly_completion(queryset, created_since) -> dict:
    """queryset: tareas (Issue). created_since: fecha de creación del workspace o proyecto en MWSTASKS."""
    first = queryset.aggregate(m=Min("created_at"))["m"]
    start = _month(min(created_since, first).date() if first else created_since.date())
    created = dict(queryset.annotate(m=TruncMonth("created_at")).values_list("m").annotate(n=Count("id", distinct=True)))
    resolved = dict(
        queryset.filter(state__group="completed", completed_at__isnull=False)
        .annotate(m=TruncMonth("completed_at")).values_list("m").annotate(n=Count("id", distinct=True))
    )
    key = lambda m: m.date().isoformat() if isinstance(m, dt.datetime) else m.isoformat()  # noqa: E731
    created = {key(k): v for k, v in created.items() if k}
    resolved = {key(k): v for k, v in resolved.items() if k}
    data, month, last = [], start, _month(timezone.now().date())
    while month <= last:
        k = month.isoformat()
        c, r = created.get(k, 0), resolved.get(k, 0)
        data.append({"key": k, "name": k, "count": c, "created_issues": c, "completed_issues": r})
        month = (month + dt.timedelta(days=32)).replace(day=1)
    return {"data": data, "schema": {"completed_issues": "completed_issues", "created_issues": "created_issues"}}


class WorkspaceCompletionChartEndpoint(AdvanceAnalyticsChartEndpoint):
    def work_item_completion_chart(self):
        queryset = Issue.issue_objects.filter(**self.filters["base_filters"])
        if self.filters["chart_period_range"]:
            start_date, end_date = self.filters["chart_period_range"]
            queryset = queryset.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
        workspace = Workspace.objects.get(slug=self._workspace_slug)
        return monthly_completion(queryset, workspace.created_at)


class ProjectCompletionChartEndpoint(ProjectAdvanceAnalyticsChartEndpoint):
    def work_item_completion_chart(self, project_id, cycle_id=None, module_id=None):
        if cycle_id is not None or module_id is not None:
            return super().work_item_completion_chart(project_id, cycle_id=cycle_id, module_id=module_id)
        project = Project.objects.filter(id=project_id).first()
        if project is None or not project.created_at:
            return {"data": [], "schema": {}}
        queryset = Issue.issue_objects.filter(**self.filters["base_filters"]).filter(project_id=project_id)
        return monthly_completion(queryset, project.created_at)
