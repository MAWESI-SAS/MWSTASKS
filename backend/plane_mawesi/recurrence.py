# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Tareas que se repiten: cálculo de fechas y creación de la siguiente ocurrencia.

Modo "complete": cuando la ocurrencia vigente se completa se crea la siguiente. Modo "schedule": se crea al llegar
su fecha de vencimiento, esté o no completa. La siguiente copia nombre, descripción (checklist sin marcar),
prioridad, responsables, etiquetas, listas, padre y campos propios; fechas corridas un período; estado inicial.
"""
import calendar
import datetime as dt
import re
from zoneinfo import ZoneInfo

from crum import impersonate
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from plane.db.models import Issue, IssueAssignee, IssueLabel, ModuleIssue, Project

from plane_mawesi.models import PropertyValue, Recurrence
from plane_mawesi.templates import create_issue

TZ = ZoneInfo("America/Bogota")
MAX_PER_RUN = 200


def today() -> dt.date:
    return timezone.now().astimezone(TZ).date()


def add_months(d: dt.date, n: int) -> dt.date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def step(d: dt.date, frequency: str, interval: int) -> dt.date:
    if frequency == "daily":
        return d + dt.timedelta(days=interval)
    if frequency == "weekly":
        return d + dt.timedelta(weeks=interval)
    if frequency == "monthly":
        return add_months(d, interval)
    # weekdays: n días hábiles (lunes a viernes)
    left = interval
    while left:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            left -= 1
    return d


def next_dates(rule, issue, now_date=None):
    """(inicio, vencimiento) de la siguiente. Nunca en el pasado: si se completó tarde, salta los períodos vencidos."""
    now_date = now_date or today()
    base = issue.target_date or issue.start_date or now_date
    target = step(base, rule.frequency, rule.interval)
    while target < now_date:
        target = step(target, rule.frequency, rule.interval)
    start = None
    if issue.start_date and issue.target_date:
        start = target - (issue.target_date - issue.start_date)
    elif issue.start_date and not issue.target_date:
        start, target = target, None
    return start, target


def is_due(rule, issue, now_date=None) -> bool:
    if rule.trigger == "schedule":
        return issue.target_date is not None and issue.target_date <= (now_date or today())
    return issue.state is not None and issue.state.group == "completed"


def unchecked(html_text: str) -> str:
    return re.sub(r'data-checked="true"', 'data-checked="false"', html_text or "")


def create_next(rule, now_date=None):
    """Crea la siguiente ocurrencia y mueve la regla a ella. Devuelve la nueva tarea."""
    issue = rule.issue
    project = Project.objects.get(pk=rule.project_id)
    start, target = next_dates(rule, issue, now_date)
    user = rule.created_by or issue.created_by
    data = {
        "name": issue.name, "priority": issue.priority, "description_html": unchecked(issue.description_html) or "<p></p>",
        "assignee_ids": [str(a) for a in IssueAssignee.objects.filter(issue=issue, deleted_at__isnull=True).values_list("assignee_id", flat=True)],
        "label_ids": [str(lb) for lb in IssueLabel.objects.filter(issue=issue, deleted_at__isnull=True).values_list("label_id", flat=True)],
        "parent_id": str(issue.parent_id) if issue.parent_id else None,
        "start_date": start.isoformat() if start else None, "target_date": target.isoformat() if target else None,
    }
    with impersonate(user):
        new = create_issue(project=project, data=data, user=user, request_host=settings.WEB_URL)
        ModuleIssue.objects.bulk_create([
            ModuleIssue(module_id=m, issue=new, project_id=new.project_id, workspace_id=new.workspace_id)
            for m in ModuleIssue.objects.filter(issue=issue, deleted_at__isnull=True).values_list("module_id", flat=True)
        ], ignore_conflicts=True)
        PropertyValue.objects.bulk_create([
            PropertyValue(issue=new, property_id=v.property_id, value=v.value, project_id=new.project_id, workspace_id=new.workspace_id)
            for v in PropertyValue.objects.filter(issue=issue, property__is_active=True)
        ])
    rule.issue = new
    rule.occurrences += 1
    rule.save(update_fields=["issue", "occurrences", "updated_at"], disable_auto_set_user=True)
    return new


def run_due(now_date=None) -> int:
    """Crea las ocurrencias que tocan. Una regla por transacción, con bloqueo: dos corridas a la vez no duplican."""
    now_date = now_date or today()
    due = Q(trigger="complete", issue__state__group="completed") | Q(trigger="schedule", issue__target_date__lte=now_date)
    ids = list(Recurrence.objects.filter(due, issue__deleted_at__isnull=True, issue__archived_at__isnull=True)
               .values_list("id", flat=True)[:MAX_PER_RUN])
    created = 0
    for rid in ids:
        with transaction.atomic():
            rule = (Recurrence.objects.select_for_update(skip_locked=True, of=("self",))
                    .select_related("issue", "issue__state").filter(pk=rid).first())
            if rule is None or not is_due(rule, rule.issue, now_date):
                continue
            create_next(rule, now_date)
            created += 1
    return created
