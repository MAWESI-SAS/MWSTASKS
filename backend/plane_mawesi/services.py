# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Lógica compartida por la API web (sesión) y la API pública (API key)."""
import datetime
from typing import Optional

from django.db.models import Sum
from django.utils import timezone

from plane.app.permissions import ROLE
from plane.db.models import Issue, IssueActivity, ProjectMember, WorkspaceMember

from plane_mawesi.models import Worklog

ACTIVITY_FIELD = "worklog"


def project_role(user, slug: str, project_id) -> Optional[int]:
    """Rol efectivo del usuario en el proyecto (los admins del workspace miembros del proyecto cuentan como admin)."""
    pm = ProjectMember.objects.filter(
        member=user, workspace__slug=slug, project_id=project_id, is_active=True
    ).values_list("role", flat=True).first()
    if pm is None:
        return None
    if WorkspaceMember.objects.filter(member=user, workspace__slug=slug, role=ROLE.ADMIN.value, is_active=True).exists():
        return ROLE.ADMIN.value
    return pm


def get_issue(slug: str, project_id, issue_id) -> Optional[Issue]:
    return Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk=issue_id).first()


def can_edit(user, role: Optional[int], worklog: Worklog) -> bool:
    if role == ROLE.ADMIN.value:
        return True
    return role == ROLE.MEMBER.value and user.id in (worklog.member_id, worklog.created_by_id)


def is_project_member(slug: str, project_id, member_id) -> bool:
    return ProjectMember.objects.filter(
        workspace__slug=slug, project_id=project_id, member_id=member_id, is_active=True
    ).exists()


def record_activity(*, worklog: Worklog, actor_id, verb: str, old_minutes: Optional[int] = None) -> None:
    """Escribe la fila de historial directamente (Plane ignora tipos desconocidos en su tarea de actividad)."""
    IssueActivity.objects.create(
        issue_id=worklog.issue_id,
        project_id=worklog.project_id,
        workspace_id=worklog.workspace_id,
        actor_id=actor_id,
        verb=verb,
        field=ACTIVITY_FIELD,
        old_value=None if old_minutes is None else str(old_minutes),
        new_value=None if verb == "deleted" else str(worklog.duration_minutes),
        new_identifier=worklog.id if verb != "deleted" else None,
        old_identifier=worklog.id if verb == "deleted" else None,
        comment=f"{verb} worklog",
        epoch=int(timezone.now().timestamp()),
    )


def totals_by_issue(slug: str, project_id, issue_ids) -> dict:
    rows = (
        Worklog.objects.filter(workspace__slug=slug, project_id=project_id, issue_id__in=issue_ids)
        .values("issue_id")
        .annotate(total=Sum("duration_minutes"))
    )
    return {str(r["issue_id"]): r["total"] for r in rows}


def parse_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    return datetime.date.fromisoformat(value)
