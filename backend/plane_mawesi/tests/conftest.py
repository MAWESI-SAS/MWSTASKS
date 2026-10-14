# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime

import pytest
from rest_framework.test import APIClient

from plane.db.models import Issue, Project, ProjectMember, State, User, WorkspaceMember

# Fixtures de Plane (create_user, workspace, session_client, api_key_client...).
from plane.tests.conftest import *  # noqa: F401,F403

ADMIN, MEMBER, GUEST = 20, 15, 5


def make_user(email):
    u = User.objects.create(email=email, username=email.split("@")[0], first_name=email.split("@")[0])
    u.set_password("x")
    u.save()
    return u


@pytest.fixture
def project(db, workspace, create_user):
    p = Project.objects.create(name="Contractor", identifier="CON", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(project=p, workspace=workspace, member=create_user, role=ADMIN)
    State.objects.create(name="Backlog", group="backlog", default=True, project=p, workspace=workspace)
    return p


@pytest.fixture
def issue(db, project):
    return Issue.objects.create(name="Tarea", project=project, workspace=project.workspace)


@pytest.fixture
def member_factory(db, workspace, project):
    def _make(email, role):
        u = make_user(email)
        WorkspaceMember.objects.create(workspace=workspace, member=u, role=role)
        ProjectMember.objects.create(project=project, workspace=workspace, member=u, role=role)
        c = APIClient()
        c.force_authenticate(user=u)
        return u, c
    return _make


@pytest.fixture
def today():
    return datetime.date.today().isoformat()
