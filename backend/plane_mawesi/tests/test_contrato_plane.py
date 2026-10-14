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
