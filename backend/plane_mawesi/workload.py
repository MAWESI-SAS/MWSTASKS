# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Carga de trabajo por persona y por día (la vista Workload de ClickUp), de todos los proyectos de quien consulta.

Mismas reglas que ClickUp (help.clickup.com, "Use Workload view" y "Set capacity limits"):
- Una tarea aparece si tiene fecha de inicio o de vencimiento. Su trabajo se reparte en partes iguales entre los días
  hábiles desde el inicio hasta el vencimiento; con una sola fecha, todo cae ese día. Sin días hábiles en el rango (una
  tarea de sábado), cae en el vencimiento.
- Trabajo = el RESTANTE de la tarea (estimado − horas hechas, o el corregido a mano; ver estimates.py). Con varios
  responsables se reparte en partes iguales (como capacity.py). Medida "tareas": cada tarea cuenta 1 en cada día.
- Capacidad = horas por día de cada persona (8 si nadie la cambió) en los días hábiles: lunes a viernes sin festivos de
  Colombia (el calendario del SLA).
- Solo tareas abiertas. Lo que no entra en la grilla va al "Sin programar" de cada persona (el Backlog de ClickUp):
  sin fechas, sin estimado y vencidas.
- Solo los proyectos donde quien consulta es admin o miembro (como Horas y la Wiki). Las personas que aparecen son las
  que tienen tareas abiertas en esos proyectos.
"""
import datetime as dt
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db.models import Sum

from plane.app.permissions import ROLE
from plane.db.models import Issue, IssueAssignee, ModuleIssue, ProjectMember, User, WorkspaceMember

from plane_mawesi import estimates as E
from plane_mawesi.models import IssueEstimate, Worklog, WorkloadCapacity
from plane_mawesi.sla import Calendar

DEFAULT_HOURS_PER_DAY = Decimal("8")
MAX_HOURS_PER_DAY = Decimal("24")
MAX_DAYS = 93  # un trimestre
MAX_TASKS = 5000
CAL = Calendar()


class InvalidWorkload(ValueError):
    pass


def visible_projects(user, slug) -> list:
    return [str(p) for p in ProjectMember.objects.filter(
        member=user, workspace__slug=slug, is_active=True, project__archived_at__isnull=True,
        role__in=(ROLE.ADMIN.value, ROLE.MEMBER.value),
    ).values_list("project_id", flat=True)]


def span(start, target):
    """(desde, hasta) de una tarea, o None sin fechas."""
    a, b = start or target, target or start
    if a is None:
        return None
    return (a, b) if a <= b else (b, a)


def spread(minutes: float, a: dt.date, b: dt.date) -> dict:
    """{fecha: minutos} repartidos en partes iguales entre los días hábiles de [a, b]."""
    days = [a + dt.timedelta(days=i) for i in range((b - a).days + 1)]
    work = [d for d in days if CAL.is_workday(d)] or [b]
    share = minutes / len(work)
    return {d: share for d in work}


def capacities(slug) -> dict:
    return {str(c.member_id): c.hours_per_day for c in WorkloadCapacity.objects.filter(workspace__slug=slug)}


def report(user, slug, start: dt.date, end: dt.date, today: dt.date, project_ids=None, module_id=None) -> dict:
    if end < start:
        raise InvalidWorkload("La fecha final va después de la inicial.")
    if (end - start).days + 1 > MAX_DAYS:
        raise InvalidWorkload(f"Hasta {MAX_DAYS} días por consulta.")
    visible = visible_projects(user, slug)
    projects = [p for p in visible if not project_ids or p in project_ids]
    qs = Issue.issue_objects.filter(workspace__slug=slug, project_id__in=projects).exclude(state__group__in=E.CLOSED_GROUPS)
    if module_id:
        qs = qs.filter(pk__in=ModuleIssue.objects.filter(module_id=module_id, deleted_at__isnull=True).values("issue_id"))
    issues = list(qs.values("id", "name", "sequence_id", "project_id", "project__identifier", "start_date", "target_date",
                            "state__group", "state__name", "priority")[:MAX_TASKS + 1])
    truncated = len(issues) > MAX_TASKS
    issues = issues[:MAX_TASKS]
    ids = [i["id"] for i in issues]
    estimates = {e.issue_id: e for e in IssueEstimate.objects.filter(issue_id__in=ids)}
    done = dict(Worklog.objects.filter(issue_id__in=ids).values("issue_id").annotate(m=Sum("duration_minutes")).values_list("issue_id", "m"))
    assignees = defaultdict(list)
    for iid, uid in IssueAssignee.objects.filter(issue_id__in=ids, deleted_at__isnull=True, assignee__is_bot=False).values_list("issue_id", "assignee_id"):
        assignees[iid].append(str(uid))

    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    caps = capacities(slug)
    rows = {}

    def row(mid):
        if mid not in rows:
            rows[mid] = {"member_id": mid, "minutes": defaultdict(float), "tasks": defaultdict(int), "items": [],
                         "backlog": {"undated": [], "unestimated": 0, "overdue": []}}
        return rows[mid]

    for i in issues:
        remaining = E.row(estimates.get(i["id"]), done.get(i["id"], 0), i["state__group"] or "")["remaining_minutes"]
        who = assignees.get(i["id"]) or [None]
        task = {"id": str(i["id"]), "key": f'{i["project__identifier"]}-{i["sequence_id"]}', "name": i["name"],
                "project_id": str(i["project_id"]), "state": i["state__name"], "priority": i["priority"],
                "start": i["start_date"].isoformat() if i["start_date"] else None,
                "end": i["target_date"].isoformat() if i["target_date"] else None,
                "remaining_minutes": remaining, "assignee_ids": [w for w in who if w]}
        s = span(i["start_date"], i["target_date"])
        for mid in who:
            r = row(mid or "")
            if s is None:
                r["backlog"]["undated"].append(task)
                continue
            if s[1] < today:
                r["backlog"]["overdue"].append(task)
            if s[1] < start or s[0] > end:
                continue
            if remaining is None:
                r["backlog"]["unestimated"] += 1
            share = (remaining or 0) / len(who)
            per_day = spread(share, s[0], s[1])
            inside = {d.isoformat(): round(m, 1) for d, m in per_day.items() if start <= d <= end}
            for d in days:
                if s[0] <= d <= s[1]:
                    r["tasks"][d.isoformat()] += 1
            for d, m in inside.items():
                r["minutes"][d] += m
            r["items"].append({**task, "share_minutes": round(share, 1), "days": inside})

    members = {str(u["id"]): u for u in User.objects.filter(pk__in=[m for m in rows if m]).values("id", "display_name", "first_name", "last_name", "avatar", "email")}
    out = []
    for mid, r in rows.items():
        hours = caps.get(mid, DEFAULT_HOURS_PER_DAY)
        cap = {d.isoformat(): (float(hours) * 60 if CAL.is_workday(d) else 0) for d in days}
        u = members.get(mid, {})
        out.append({
            "member_id": mid or None, "display_name": u.get("display_name") or "", "email": u.get("email") or "",
            "hours_per_day": float(hours), "capacity": cap,
            "minutes": {k: round(v, 1) for k, v in r["minutes"].items()}, "tasks": dict(r["tasks"]),
            "total_minutes": round(sum(r["minutes"].values()), 1), "capacity_minutes": sum(cap.values()),
            "items": sorted(r["items"], key=lambda x: (x["start"] or x["end"] or "", x["key"])),
            "backlog": {"undated": r["backlog"]["undated"][:200], "undated_count": len(r["backlog"]["undated"]),
                        "overdue": r["backlog"]["overdue"][:200], "overdue_count": len(r["backlog"]["overdue"]),
                        "unestimated": r["backlog"]["unestimated"]},
        })
    out.sort(key=lambda x: (x["member_id"] is None, (x["display_name"] or "").lower()))
    return {"from": start.isoformat(), "to": end.isoformat(), "today": today.isoformat(),
            "days": [{"date": d.isoformat(), "workday": CAL.is_workday(d)} for d in days],
            "default_hours_per_day": float(DEFAULT_HOURS_PER_DAY), "rows": out, "truncated": truncated,
            "project_ids": projects}


def set_capacity(slug, member_id, hours, actor) -> dict:
    try:
        hours = Decimal(str(hours)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise InvalidWorkload("Horas por día: escribe un número.")
    if not Decimal(0) <= hours <= MAX_HOURS_PER_DAY:
        raise InvalidWorkload("Horas por día: de 0 a 24.")
    wm = WorkspaceMember.objects.filter(workspace__slug=slug, member_id=member_id, is_active=True).select_related("workspace").first()
    if wm is None:
        raise InvalidWorkload("La persona no es miembro del workspace.")
    cap, _ = WorkloadCapacity.objects.update_or_create(
        workspace=wm.workspace, member_id=member_id,
        defaults={"hours_per_day": hours, "updated_by": actor},
        create_defaults={"hours_per_day": hours, "created_by": actor, "updated_by": actor},
    )
    return {"member_id": str(member_id), "hours_per_day": float(cap.hours_per_day)}
