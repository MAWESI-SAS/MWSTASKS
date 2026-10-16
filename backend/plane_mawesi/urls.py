# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Rutas MAWESI primero; después todas las de Plane, sin tocarlas."""
from django.urls import path

from plane.urls import urlpatterns as plane_urlpatterns

from plane_mawesi.auth import views as auth
from plane_mawesi.views import properties as pr
from plane_mawesi.views import sla as sl
from plane_mawesi.views import table as tb
from plane_mawesi.views import templates as tp
from plane_mawesi.views import timers as tm
from plane_mawesi.views import wiki as wk
from plane_mawesi.views import worklogs as w

handler404 = "plane.app.views.error_404.custom_404_view"

PROJECT = "workspaces/<str:slug>/projects/<uuid:project_id>"
ISSUE = f"{PROJECT}/issues/<uuid:issue_id>"


def _routes(prefix: str, issue_view, detail_view, totals_view, report_view, suffix: str):
    return [
        path(f"{prefix}{ISSUE}/worklogs/", issue_view.as_view(), name=f"mawesi-worklogs{suffix}"),
        path(f"{prefix}{ISSUE}/worklogs/<uuid:pk>/", detail_view.as_view(), name=f"mawesi-worklog-detail{suffix}"),
        path(f"{prefix}{PROJECT}/worklogs/totals/", totals_view.as_view(), name=f"mawesi-worklog-totals{suffix}"),
        path(f"{prefix}workspaces/<str:slug>/worklogs/report/", report_view.as_view(), name=f"mawesi-worklog-report{suffix}"),
    ]


def _property_routes(prefix: str, list_view, detail_view, values_view, batch_view, suffix: str):
    return [
        path(f"{prefix}{PROJECT}/properties/", list_view.as_view(), name=f"mawesi-properties{suffix}"),
        path(f"{prefix}{PROJECT}/properties/<uuid:property_id>/", detail_view.as_view(), name=f"mawesi-property{suffix}"),
        path(f"{prefix}{ISSUE}/property-values/", values_view.as_view(), name=f"mawesi-issue-values{suffix}"),
        path(f"{prefix}{PROJECT}/property-values/", batch_view.as_view(), name=f"mawesi-values-batch{suffix}"),
    ]


urlpatterns = [
    path("api/mawesi/ping/", w.PingEndpoint.as_view(), name="mawesi-ping"),
    # Login con Microsoft (Plane CE no lo trae). Mismo prefijo /auth/ que los logins de Plane.
    path("auth/microsoft/", auth.MicrosoftInitiateEndpoint.as_view(), name="mawesi-microsoft-initiate"),
    path("auth/microsoft/callback/", auth.MicrosoftCallbackEndpoint.as_view(), name="mawesi-microsoft-callback"),
    path("api/mawesi/auth-providers/", auth.AuthProvidersEndpoint.as_view(), name="mawesi-auth-providers"),
    *_routes("api/mawesi/", w.IssueWorklogsEndpoint, w.WorklogDetailEndpoint, w.WorklogTotalsEndpoint, w.WorklogReportEndpoint, ""),
    *_routes("api/v1/mawesi/", w.IssueWorklogsKeyEndpoint, w.WorklogDetailKeyEndpoint, w.WorklogTotalsKeyEndpoint, w.WorklogReportKeyEndpoint, "-key"),
    path(f"api/mawesi/{PROJECT}/table/", tb.ProjectTableEndpoint.as_view(), name="mawesi-table"),
    path("api/mawesi/workspaces/<str:slug>/wiki/", wk.WikiEndpoint.as_view(), name="mawesi-wiki"),
    # SLA: plazo por prioridad en horas hábiles y tiempo en cada estado (solo web).
    path(f"api/mawesi/{PROJECT}/sla/", sl.SlaPolicyEndpoint.as_view(), name="mawesi-sla-policy"),
    path(f"api/mawesi/{PROJECT}/sla/issues/", sl.SlaBatchEndpoint.as_view(), name="mawesi-sla-batch"),
    path(f"api/mawesi/{ISSUE}/sla/", sl.IssueSlaEndpoint.as_view(), name="mawesi-sla-issue"),
    # Plantillas de tarea (solo web).
    path(f"api/mawesi/{PROJECT}/templates/", tp.TemplatesEndpoint.as_view(), name="mawesi-templates"),
    path(f"api/mawesi/{PROJECT}/templates/<uuid:template_id>/", tp.TemplateDetailEndpoint.as_view(), name="mawesi-template"),
    path(f"api/mawesi/{PROJECT}/templates/<uuid:template_id>/apply/", tp.ApplyTemplateEndpoint.as_view(), name="mawesi-template-apply"),
    # Cronómetro: solo la web (lo usa una persona desde el navegador).
    path("api/mawesi/workspaces/<str:slug>/timer/", tm.CurrentTimerEndpoint.as_view(), name="mawesi-timer"),
    path("api/mawesi/workspaces/<str:slug>/timer/stop/", tm.StopTimerEndpoint.as_view(), name="mawesi-timer-stop"),
    path(f"api/mawesi/{ISSUE}/timer/start/", tm.StartTimerEndpoint.as_view(), name="mawesi-timer-start"),
    *_property_routes("api/mawesi/", pr.PropertiesEndpoint, pr.PropertyDetailEndpoint, pr.IssueValuesEndpoint, pr.ValuesBatchEndpoint, ""),
    *_property_routes("api/v1/mawesi/", pr.PropertiesKeyEndpoint, pr.PropertyDetailKeyEndpoint, pr.IssueValuesKeyEndpoint, pr.ValuesBatchKeyEndpoint, "-key"),
    *plane_urlpatterns,
]
