# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Estimado, hecho y restante en horas (Original Estimate / Completed Work / Remaining Work de Azure DevOps).

- Estimado: lo carga la persona.
- Hecho: suma de las horas registradas (Worklog), no se escribe a mano.
- Restante: si nadie lo tocó, estimado − hecho (nunca menos de 0). Si alguien lo corrige, vale lo corregido hasta
  que se borre la corrección. Una tarea terminada o cancelada tiene 0 restante.
"""
from typing import Optional

from django.db import transaction
from django.utils import timezone

from plane.db.models import IssueActivity

from plane_mawesi import services
from plane_mawesi.models import IssueEstimate

MAX_MINUTES = 10_000 * 60
ACTIVITY_FIELD = "estimate_hours"
CLOSED_GROUPS = ("completed", "cancelled")


def row(estimate: Optional[IssueEstimate], completed: int, state_group: str) -> dict:
    original = estimate.original_minutes if estimate else None
    manual = estimate.remaining_minutes if estimate else None
    if state_group in CLOSED_GROUPS:
        remaining = 0
    elif manual is not None:
        remaining = manual
    elif original is not None:
        remaining = max(0, original - completed)
    else:
        remaining = None
    return {
        "original_minutes": original,
        "remaining_minutes": remaining,
        "remaining_is_manual": manual is not None and state_group not in CLOSED_GROUPS,
        "completed_minutes": completed,
    }


def rows_for(slug, project_id, issues) -> dict:
    """{issue_id: fila} para `issues` = [{"id", "state__group"}]. Solo las que tienen estimado o corrección."""
    ids = [i["id"] for i in issues]
    estimates = {str(e.issue_id): e for e in IssueEstimate.objects.filter(workspace__slug=slug, project_id=project_id, issue_id__in=ids)}
    if not estimates:
        return {}
    done = services.totals_by_issue(slug, project_id, list(estimates))
    return {
        str(i["id"]): row(estimates[str(i["id"])], done.get(str(i["id"]), 0), i["state__group"] or "")
        for i in issues if str(i["id"]) in estimates
    }


class InvalidEstimate(ValueError):
    pass


def _minutes(value, name) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        minutes = int(round(float(value)))
    except (TypeError, ValueError):
        raise InvalidEstimate(f"{name}: escribe un número de minutos.")
    if not 0 <= minutes <= MAX_MINUTES:
        raise InvalidEstimate(f"{name}: va de 0 a {MAX_MINUTES // 60} horas.")
    return minutes


def save(issue, data: dict, actor_id) -> IssueEstimate:
    """Guarda lo que venga en `data` ("original_minutes" y/o "remaining_minutes"; null borra) y deja historial."""
    fields = {k: _minutes(data[k], k) for k in ("original_minutes", "remaining_minutes") if k in data}
    if not fields:
        raise InvalidEstimate("Enviar original_minutes y/o remaining_minutes.")
    with transaction.atomic():
        est = IssueEstimate.objects.select_for_update().filter(issue=issue).first() or IssueEstimate(
            issue=issue, project_id=issue.project_id, workspace_id=issue.workspace_id, created_by_id=actor_id)
        old = est.original_minutes
        for k, v in fields.items():
            setattr(est, k, v)
        est.updated_by_id = actor_id
        est.save()
        if "original_minutes" in fields and old != est.original_minutes:
            IssueActivity.objects.create(
                issue_id=issue.id, project_id=issue.project_id, workspace_id=issue.workspace_id, actor_id=actor_id,
                verb="updated", field=ACTIVITY_FIELD, old_value=None if old is None else str(old),
                new_value=None if est.original_minutes is None else str(est.original_minutes),
                comment="updated estimate", epoch=int(timezone.now().timestamp()),
            )
    return est
