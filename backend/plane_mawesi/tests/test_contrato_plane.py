# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Contratos con los internos de Plane que usamos. Si una actualización de Plane los cambia, falla aquí primero."""
import inspect

import pytest


@pytest.mark.contract
def test_permisos_y_roles():
    from plane.app.permissions import ROLE, allow_permission  # noqa: F401
    assert (ROLE.ADMIN.value, ROLE.MEMBER.value, ROLE.GUEST.value) == (20, 15, 5)


@pytest.mark.contract
def test_bases_de_vistas():
    from plane.api.views.base import BaseAPIView as KeyBase
    from plane.app.views.base import BaseAPIView as SessionBase
    from plane.api.middleware.api_authentication import APIKeyAuthentication
    assert APIKeyAuthentication in KeyBase.authentication_classes
    assert SessionBase is not None


@pytest.mark.contract
def test_campos_de_issue_activity():
    from plane.db.models import IssueActivity
    campos = {f.name for f in IssueActivity._meta.get_fields()}
    assert {"issue", "project", "workspace", "actor", "verb", "field", "old_value", "new_value",
            "old_identifier", "new_identifier", "comment", "epoch"} <= campos


@pytest.mark.contract
def test_modelos_base_y_manager_de_issues():
    from plane.db.models import Issue
    from plane.db.models.project import ProjectBaseModel
    assert hasattr(Issue, "issue_objects")
    assert {"project", "workspace"} <= {f.name for f in ProjectBaseModel._meta.get_fields()}


@pytest.mark.contract
def test_celery_lee_settings_al_importar():
    """Motivo del cambio temporal de DJANGO_SETTINGS_MODULE en settings.py: si Plane deja de hacerlo, se puede quitar."""
    import plane.celery as c
    assert "redis_instance()" in inspect.getsource(c)


@pytest.mark.contract
def test_molde_oauth_para_microsoft():
    """auth/microsoft.py hereda OauthAdapter y reusa el flujo de login de Plane."""
    from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException  # noqa: F401
    from plane.authentication.adapter.oauth import OauthAdapter
    from plane.authentication.utils.host import base_host  # noqa: F401
    from plane.authentication.utils.login import user_login  # noqa: F401
    from plane.authentication.utils.redirection_path import get_redirection_path  # noqa: F401
    from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow  # noqa: F401
    from plane.utils.path_validator import get_safe_redirect_url  # noqa: F401
    params = list(inspect.signature(OauthAdapter.__init__).parameters)
    assert params[:9] == ["self", "request", "provider", "client_id", "scope", "redirect_uri", "auth_url",
                          "token_url", "userinfo_url"]
    assert {"get_user_token", "get_user_response", "create_update_account", "complete_login_or_signup"} <= set(dir(OauthAdapter))
    assert {"AUTHENTICATION_FAILED", "OAUTH_NOT_CONFIGURED", "INSTANCE_NOT_CONFIGURED"} <= set(AUTHENTICATION_ERROR_CODES)


@pytest.mark.contract
def test_almacenamiento_y_assets_para_logo_de_proyecto():
    """views/project_logo.py: sube con S3Storage().upload_file y sirve por la URL estática de PROJECT_COVER."""
    from plane.db.models import FileAsset
    from plane.settings.storage import S3Storage
    from plane.utils.exception_logger import log_exception  # noqa: F401
    assert {"file_obj", "object_name", "content_type"} <= set(inspect.signature(S3Storage.upload_file).parameters)
    assert "request" in inspect.signature(S3Storage.__init__).parameters
    a = FileAsset(id="00000000-0000-0000-0000-000000000001", entity_type=FileAsset.EntityTypeContext.PROJECT_COVER)
    assert a.asset_url == "/api/assets/v2/static/00000000-0000-0000-0000-000000000001/"
    campos = {f.name for f in FileAsset._meta.get_fields()}
    assert {"asset", "workspace", "project", "entity_type", "entity_identifier", "attributes", "size", "is_uploaded"} <= campos


@pytest.mark.contract
def test_ciclos_estados_y_responsables_para_capacidad_y_flujo():
    """capacity.py y flow.py leen fechas de ciclos, grupos de estado y responsables directo del ORM."""
    from plane.db.models import Cycle, CycleIssue, IssueAssignee, State
    from plane.db.models.workspace import WorkspaceBaseModel
    assert {"start_date", "end_date", "timezone", "archived_at"} <= {f.name for f in Cycle._meta.get_fields()}
    assert {"cycle", "issue"} <= {f.name for f in CycleIssue._meta.get_fields()}
    assert {"issue", "assignee"} <= {f.name for f in IssueAssignee._meta.get_fields()}
    assert {"group", "sequence", "default"} <= {f.name for f in State._meta.get_fields()}
    assert {"workspace", "project"} <= {f.name for f in WorkspaceBaseModel._meta.get_fields()}
    from plane.db.models import Project
    assert "timezone" in {f.name for f in Project._meta.get_fields()}  # capacity.cycle_dates


@pytest.mark.contract
@pytest.mark.django_db
def test_issue_save_marca_completed_at(workspace, create_user):
    """code.py cierra tareas con issue.save(): Plane debe seguir poniendo completed_at al pasar a "completed"."""
    from plane.db.models import Issue, Project, State
    p = Project.objects.create(name="P", identifier="PCT", workspace=workspace, created_by=create_user)
    done = State.objects.create(name="Done", group="completed", project=p, workspace=workspace)
    i = Issue.objects.create(name="x", project=p, workspace=workspace)
    i.state = done
    i.save()
    assert i.completed_at is not None


@pytest.mark.contract
def test_rutas_que_tapan_las_dependencias():
    """urls.GUARDED repite estas rutas de Plane con el control de dependencias delante. Si Plane las mueve o cambia
    sus métodos, el control dejaría de aplicarse sin avisar."""
    from django.urls import resolve

    from plane.api.views import IssueDetailAPIEndpoint, IssueRelationListCreateAPIEndpoint
    from plane.app.views import IssueRelationViewSet, IssueViewSet
    from plane.urls import urlpatterns  # noqa: F401  (Plane sigue exponiendo sus rutas)

    from plane_mawesi.views import dependencies as dp

    ids = "00000000-0000-0000-0000-000000000001"
    base = f"workspaces/ws/projects/{ids}"
    expected = {
        f"/api/{base}/issues/{ids}/": dp.GuardedIssueViewSet,
        f"/api/v1/{base}/issues/{ids}/": dp.GuardedIssueDetailKeyEndpoint,
        f"/api/v1/{base}/work-items/{ids}/": dp.GuardedIssueDetailKeyEndpoint,
        f"/api/{base}/issues/{ids}/issue-relation/": dp.GuardedIssueRelationViewSet,
        f"/api/v1/{base}/work-items/{ids}/relations/": dp.GuardedIssueRelationKeyEndpoint,
    }
    for path, view in expected.items():
        assert resolve(path).func.cls is view, path
    assert {"partial_update", "update", "retrieve", "destroy"} <= set(dir(IssueViewSet))
    assert "patch" in dir(IssueDetailAPIEndpoint) and "post" in dir(IssueRelationListCreateAPIEndpoint)
    assert "create" in dir(IssueRelationViewSet)


@pytest.mark.contract
def test_tipos_de_plane_para_tipos_de_tarea():
    """types.py usa db.IssueType + ProjectIssueType + Issue.type. La API pública de Plane, al crear, toma el tipo con
    IssueType.is_default (por eso nunca lo marcamos) y Plane saca de sus listas las tareas de tipo épica."""
    import inspect

    from plane.api.serializers.issue import IssueSerializer
    from plane.db.models import Issue, IssueType
    from plane.db.models.issue_type import ProjectIssueType

    fields = {f.name for f in IssueType._meta.get_fields()}
    assert {"workspace", "name", "description", "logo_props", "is_epic", "is_default", "is_active", "deleted_at"} <= fields
    assert {"project", "issue_type", "is_default", "level", "deleted_at"} <= {f.name for f in ProjectIssueType._meta.get_fields()}
    assert Issue._meta.get_field("type").related_model is IssueType
    src = inspect.getsource(IssueSerializer.create)
    assert "project_issue_types__project_id=project_id, is_default=True" in src
