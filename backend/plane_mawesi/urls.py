# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Rutas MAWESI primero; después todas las de Plane, sin tocarlas."""
from django.urls import path

from plane.urls import urlpatterns as plane_urlpatterns

from plane_mawesi.auth import views as auth
from plane_mawesi.views import properties as pr
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
    *_property_routes("api/mawesi/", pr.PropertiesEndpoint, pr.PropertyDetailEndpoint, pr.IssueValuesEndpoint, pr.ValuesBatchEndpoint, ""),
    *_property_routes("api/v1/mawesi/", pr.PropertiesKeyEndpoint, pr.PropertyDetailKeyEndpoint, pr.IssueValuesKeyEndpoint, pr.ValuesBatchKeyEndpoint, "-key"),
    *plane_urlpatterns,
]
