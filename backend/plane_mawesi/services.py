# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Lógica compartida por la API web (sesión) y la API pública (API key)."""
import datetime
from typing import Optional

from django.db.models import F, OuterRef, Subquery, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from plane.app.permissions import ROLE
from plane.db.models import Issue, IssueActivity, ModuleIssue, ProjectMember, WorkspaceMember

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


# by → (campo de la clave, campo del nombre). "module" toma la primera lista de la tarea para no contar 2 veces.
SUMMARY_GROUPS = {
    "project": ("project_id", "project__name"),
    "member": ("member_id", "member__display_name"),
    "module": ("module_key", "module_name"),
}


def monthly_summary(rows, by: str) -> dict:
    """Minutos por grupo y por mes ("AAAA-MM"), sumados en la base. Grupos de mayor a menor total."""
    key, label = SUMMARY_GROUPS[by]
    if by == "module":
        first = ModuleIssue.objects.filter(issue_id=OuterRef("issue_id"), deleted_at__isnull=True).order_by("created_at")
        rows = rows.annotate(
            module_key=Subquery(first.values("module_id")[:1]),
            module_name=Subquery(first.values("module__name")[:1]),
        )
    sums = (
        rows.annotate(month=TruncMonth("date"))
        .values(key, label, "project_id", "month")
        .annotate(minutes=Sum("duration_minutes"), project_identifier=F("project__identifier"))
        .order_by()
    )
    groups, months = {}, set()
    for r in sums:
        month = r["month"].strftime("%Y-%m")
        months.add(month)
        # Sin lista: una fila por proyecto ("TQ · Sin lista"), no una sola mezclada.
        gid = str(r[key] or f"none-{r['project_id']}")
        g = groups.setdefault(gid, {"key": gid, "label": r[label] or "", "project_id": None, "project_identifier": None, "cells": {}, "total": 0})
        if by != "member":
            g["project_id"], g["project_identifier"] = str(r["project_id"]), r["project_identifier"]
        g["cells"][month] = g["cells"].get(month, 0) + r["minutes"]
        g["total"] += r["minutes"]
    ordered = sorted(groups.values(), key=lambda g: (-g["total"], g["label"]))
    return {"by": by, "months": sorted(months), "groups": ordered, "total_minutes": sum(g["total"] for g in ordered)}
