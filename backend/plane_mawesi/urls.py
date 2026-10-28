# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Rutas MAWESI primero; después todas las de Plane, sin tocarlas."""
from django.urls import path

from plane.urls import urlpatterns as plane_urlpatterns

from plane_mawesi import tokens
from plane_mawesi.auth import views as auth
from plane_mawesi.views import analytics as an
from plane_mawesi.views import apidocs
from plane_mawesi.views import automations as au
from plane_mawesi.views import board as bd
from plane_mawesi.views import capacity as cp
from plane_mawesi.views import code as cd
from plane_mawesi.views import comments as cm
from plane_mawesi.views import dependencies as dp
from plane_mawesi.views import estimates as es
from plane_mawesi.views import favicons as fv
from plane_mawesi.views import flow as fl
from plane_mawesi.views import properties as pr
from plane_mawesi.views import project_logo as pl
from plane_mawesi.views import recurrence as rc
from plane_mawesi.views import relations as rl
from plane_mawesi.views import sla as sl
from plane_mawesi.views import table as tb
from plane_mawesi.views import templates as tp
from plane_mawesi.views import timers as tm
from plane_mawesi.views import types as ty
from plane_mawesi.views import wiki as wk
from plane_mawesi.views import worklogs as w

handler404 = "plane.app.views.error_404.custom_404_view"

PROJECT = "workspaces/<str:slug>/projects/<uuid:project_id>"
ISSUE = f"{PROJECT}/issues/<uuid:issue_id>"


def _routes(prefix: str, issue_view, detail_view, totals_view, report_view, summary_view, suffix: str):
    return [
        path(f"{prefix}{ISSUE}/worklogs/", issue_view.as_view(), name=f"mawesi-worklogs{suffix}"),
        path(f"{prefix}{ISSUE}/worklogs/<uuid:pk>/", detail_view.as_view(), name=f"mawesi-worklog-detail{suffix}"),
        path(f"{prefix}{PROJECT}/worklogs/totals/", totals_view.as_view(), name=f"mawesi-worklog-totals{suffix}"),
        path(f"{prefix}workspaces/<str:slug>/worklogs/report/", report_view.as_view(), name=f"mawesi-worklog-report{suffix}"),
        path(f"{prefix}workspaces/<str:slug>/worklogs/summary/", summary_view.as_view(), name=f"mawesi-worklog-summary{suffix}"),
    ]


def _property_routes(prefix: str, list_view, detail_view, values_view, batch_view, suffix: str):
    return [
        path(f"{prefix}{PROJECT}/properties/", list_view.as_view(), name=f"mawesi-properties{suffix}"),
        path(f"{prefix}{PROJECT}/properties/<uuid:property_id>/", detail_view.as_view(), name=f"mawesi-property{suffix}"),
        path(f"{prefix}{ISSUE}/property-values/", values_view.as_view(), name=f"mawesi-issue-values{suffix}"),
        path(f"{prefix}{PROJECT}/property-values/", batch_view.as_view(), name=f"mawesi-values-batch{suffix}"),
    ]


# Las vistas de Plane que cambian estados o crean relaciones, con el control de dependencias delante (mismas rutas y
# mismos métodos que en plane/app/urls/issue.py y plane/api/urls/work_item.py; lo cubre test_contrato_plane.py).
GUARDED = [
    path(f"api/{PROJECT}/issues/<uuid:pk>/",
         dp.GuardedIssueViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}),
         name="project-issue"),
    path(f"api/v1/{PROJECT}/issues/<uuid:pk>/",
         dp.GuardedIssueDetailKeyEndpoint.as_view(http_method_names=["get", "patch", "delete"]), name="issue"),
    path(f"api/v1/{PROJECT}/work-items/<uuid:pk>/",
         dp.GuardedIssueDetailKeyEndpoint.as_view(http_method_names=["get", "patch", "delete"]), name="work-item-detail"),
    path(f"api/{ISSUE}/issue-relation/",
         dp.GuardedIssueRelationViewSet.as_view({"get": "list", "post": "create"}), name="issue-relation"),
    path(f"api/v1/{PROJECT}/work-items/<uuid:issue_id>/relations/",
         dp.GuardedIssueRelationKeyEndpoint.as_view(http_method_names=["get", "post"]), name="work-item-relation-list"),
]

# Analytics → "Created vs Resolved" con la historia migrada y "Resolved" por fecha de cierre (ver views/analytics.py).
ANALYTICS = [
    path("api/workspaces/<str:slug>/advance-analytics-charts/", an.WorkspaceCompletionChartEndpoint.as_view(),
         name="advance-analytics-chart"),
    path("api/workspaces/<str:slug>/projects/<uuid:project_id>/advance-analytics-charts/",
         an.ProjectCompletionChartEndpoint.as_view(), name="project-advance-analytics-chart"),
]

# Todas las rutas de la web aceptan también el token personal, con los permisos de su dueño (ver tokens.py).
urlpatterns = tokens.with_tokens([
    *GUARDED,
    *ANALYTICS,
    path("api/mawesi/ping/", w.PingEndpoint.as_view(), name="mawesi-ping"),
    # Documentación de toda la API (OpenAPI): página para el navegador y el schema en JSON o YAML (ver plane_mawesi/apidocs.py).
    path("api/mawesi/docs/", apidocs.ApiDocsEndpoint.as_view(), name="mawesi-api-docs"),
    path("api/mawesi/docs/schema/", apidocs.ApiSchemaEndpoint.as_view(), name="mawesi-api-schema"),
    # Login con Microsoft (Plane CE no lo trae). Mismo prefijo /auth/ que los logins de Plane.
    path("auth/microsoft/", auth.MicrosoftInitiateEndpoint.as_view(), name="mawesi-microsoft-initiate"),
    path("auth/microsoft/callback/", auth.MicrosoftCallbackEndpoint.as_view(), name="mawesi-microsoft-callback"),
    path("api/mawesi/auth-providers/", auth.AuthProvidersEndpoint.as_view(), name="mawesi-auth-providers"),
    *_routes("api/mawesi/", w.IssueWorklogsEndpoint, w.WorklogDetailEndpoint, w.WorklogTotalsEndpoint, w.WorklogReportEndpoint, w.WorklogSummaryEndpoint, ""),
    *_routes("api/v1/mawesi/", w.IssueWorklogsKeyEndpoint, w.WorklogDetailKeyEndpoint, w.WorklogTotalsKeyEndpoint, w.WorklogReportKeyEndpoint, w.WorklogSummaryKeyEndpoint, "-key"),
    path(f"api/mawesi/{PROJECT}/table/", tb.ProjectTableEndpoint.as_view(), name="mawesi-table"),
    path("api/mawesi/workspaces/<str:slug>/wiki/", wk.WikiEndpoint.as_view(), name="mawesi-wiki"),
    # SLA: plazo por prioridad en horas hábiles y tiempo en cada estado.
    path(f"api/mawesi/{PROJECT}/sla/", sl.SlaPolicyEndpoint.as_view(), name="mawesi-sla-policy"),
    path(f"api/mawesi/{PROJECT}/sla/issues/", sl.SlaBatchEndpoint.as_view(), name="mawesi-sla-batch"),
    path(f"api/mawesi/{ISSUE}/sla/", sl.IssueSlaEndpoint.as_view(), name="mawesi-sla-issue"),
    # Plantillas de tarea.
    path(f"api/mawesi/{PROJECT}/templates/", tp.TemplatesEndpoint.as_view(), name="mawesi-templates"),
    path(f"api/mawesi/{PROJECT}/templates/<uuid:template_id>/", tp.TemplateDetailEndpoint.as_view(), name="mawesi-template"),
    path(f"api/mawesi/{PROJECT}/templates/<uuid:template_id>/apply/", tp.ApplyTemplateEndpoint.as_view(), name="mawesi-template-apply"),
    path(f"api/mawesi/{ISSUE}/recurrence/", rc.IssueRecurrenceEndpoint.as_view(), name="mawesi-recurrence"),
    # Reglas automáticas.
    path(f"api/mawesi/{PROJECT}/automations/", au.AutomationsEndpoint.as_view(), name="mawesi-automations"),
    path(f"api/mawesi/{PROJECT}/automations/<uuid:rule_id>/", au.AutomationDetailEndpoint.as_view(), name="mawesi-automation"),
    # Estimado y restante en horas (web y API key: los empleados AI también estiman).
    path(f"api/mawesi/{PROJECT}/types/", ty.TypesEndpoint.as_view(), name="mawesi-types"),
    path(f"api/mawesi/{PROJECT}/types/<uuid:type_id>/", ty.TypeDetailEndpoint.as_view(), name="mawesi-type"),
    path(f"api/mawesi/{PROJECT}/issue-types/", ty.IssueTypesBatchEndpoint.as_view(), name="mawesi-issue-types"),
    path(f"api/mawesi/{ISSUE}/type/", ty.IssueTypeEndpoint.as_view(), name="mawesi-issue-type"),
    path(f"api/v1/mawesi/{PROJECT}/types/", ty.TypesKeyEndpoint.as_view(), name="mawesi-types-key"),
    path(f"api/v1/mawesi/{PROJECT}/issue-types/", ty.IssueTypesBatchKeyEndpoint.as_view(), name="mawesi-issue-types-key"),
    path(f"api/v1/mawesi/{ISSUE}/type/", ty.IssueTypeKeyEndpoint.as_view(), name="mawesi-issue-type-key"),
    path(f"api/mawesi/{ISSUE}/estimate/", es.IssueEstimateEndpoint.as_view(), name="mawesi-estimate"),
    path(f"api/mawesi/{PROJECT}/estimates/", es.EstimatesBatchEndpoint.as_view(), name="mawesi-estimates"),
    path(f"api/v1/mawesi/{ISSUE}/estimate/", es.IssueEstimateKeyEndpoint.as_view(), name="mawesi-estimate-key"),
    path(f"api/v1/mawesi/{PROJECT}/estimates/", es.EstimatesBatchKeyEndpoint.as_view(), name="mawesi-estimates-key"),
    # Último comentario por tarea, en lote (Hub: resumen del informe de mejoras).
    path(f"api/mawesi/{PROJECT}/last-comments/", cm.LastCommentsEndpoint.as_view(), name="mawesi-last-comments"),
    path(f"api/v1/mawesi/{PROJECT}/last-comments/", cm.LastCommentsKeyEndpoint.as_view(), name="mawesi-last-comments-key"),
    # Dependencias: bloqueos y fechas que chocan, para las tarjetas.
    path(f"api/mawesi/{PROJECT}/dependencies/", dp.DependencyStatusEndpoint.as_view(), name="mawesi-dependencies"),
    # Tablero: límites WIP, definición de terminado y colores de tarjeta.
    path(f"api/mawesi/{PROJECT}/board/", bd.BoardConfigEndpoint.as_view(), name="mawesi-board"),
    # Capacidad por ciclo y analítica de flujo.
    path(f"api/mawesi/{PROJECT}/capacity/cycles/", cp.CycleListEndpoint.as_view(), name="mawesi-capacity-cycles"),
    path(f"api/mawesi/{PROJECT}/cycles/<uuid:cycle_id>/capacity/", cp.CycleCapacityEndpoint.as_view(), name="mawesi-capacity"),
    path(f"api/mawesi/{PROJECT}/flow/", fl.ProjectFlowEndpoint.as_view(), name="mawesi-flow"),
    # Enlace con el código: repositorios del workspace y commits/PRs de cada tarea.
    path("api/mawesi/workspaces/<str:slug>/favicon/", fv.FaviconEndpoint.as_view(), name="mawesi-favicon"),
    path("api/mawesi/workspaces/<str:slug>/code-repos/", cd.CodeReposEndpoint.as_view(), name="mawesi-code-repos"),
    path("api/mawesi/workspaces/<str:slug>/code-repos/<uuid:repo_id>/", cd.CodeRepoDetailEndpoint.as_view(), name="mawesi-code-repo"),
    path("api/mawesi/workspaces/<str:slug>/code-repos/<uuid:repo_id>/sync/", cd.CodeRepoSyncEndpoint.as_view(), name="mawesi-code-repo-sync"),
    path(f"api/mawesi/{ISSUE}/code-links/", cd.IssueCodeLinksEndpoint.as_view(), name="mawesi-code-links"),
    # Logo del proyecto con imagen propia.
    path(f"api/mawesi/{PROJECT}/logo/", pl.ProjectLogoEndpoint.as_view(), name="mawesi-project-logo"),
    # Cronómetro.
    path("api/mawesi/workspaces/<str:slug>/timer/", tm.CurrentTimerEndpoint.as_view(), name="mawesi-timer"),
    path("api/mawesi/workspaces/<str:slug>/timer/stop/", tm.StopTimerEndpoint.as_view(), name="mawesi-timer-stop"),
    path(f"api/mawesi/{ISSUE}/timer/start/", tm.StartTimerEndpoint.as_view(), name="mawesi-timer-start"),
    *_property_routes("api/mawesi/", pr.PropertiesEndpoint, pr.PropertyDetailEndpoint, pr.IssueValuesEndpoint, pr.ValuesBatchEndpoint, ""),
    # Relaciones en lote por id externo (migración y copia incremental desde ClickUp).
    path("api/v1/mawesi/workspaces/<str:slug>/relations/", rl.RelationsBatchKeyEndpoint.as_view(), name="mawesi-relations-key"),
    *_property_routes("api/v1/mawesi/", pr.PropertiesKeyEndpoint, pr.PropertyDetailKeyEndpoint, pr.IssueValuesKeyEndpoint, pr.ValuesBatchKeyEndpoint, "-key"),
    *plane_urlpatterns,
])
