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
