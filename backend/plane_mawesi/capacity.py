# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Capacidad de un ciclo (Capacity de Azure DevOps): horas que tiene cada persona contra el trabajo que le queda.

- Días hábiles: los del calendario del SLA del proyecto (o lunes a viernes con festivos de Colombia), menos los días
  libres del equipo y los de cada persona.
- Capacidad que queda = horas por día × días hábiles desde hoy (o desde el inicio, si no empezó) hasta el fin.
- Trabajo asignado = suma del restante (ver estimates.py) de las tareas abiertas del ciclo. Una tarea con varios
  responsables se reparte en partes iguales. Las que no tienen estimado se cuentan aparte.
"""
import datetime as dt
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum

from plane.db.models import CycleIssue, Issue, IssueAssignee, ProjectMember

from plane_mawesi import estimates as E
from plane_mawesi.models import CycleCapacity, CyclePlan, IssueEstimate, SlaPolicy, Worklog
from plane_mawesi.views.sla import calendar_of

MAX_HOURS_PER_DAY = Decimal("24")
MAX_DAYS_OFF = 200


class InvalidCapacity(ValueError):
    pass


def cycle_dates(cycle):
    """(inicio, fin) como fechas en la zona del ciclo; None si le falta alguna."""
    if not cycle.start_date or not cycle.end_date:
        return None
    try:
        zone = ZoneInfo(cycle.timezone or "UTC")
    except Exception:  # noqa: BLE001 - zona rara guardada por Plane
        zone = ZoneInfo("UTC")
    return cycle.start_date.astimezone(zone).date(), cycle.end_date.astimezone(zone).date()


def workdays(cal, start: dt.date, end: dt.date, off: set) -> int:
    n, day = 0, start
    while day <= end:
        if cal.is_workday(day) and day.isoformat() not in off:
            n += 1
        day += dt.timedelta(days=1)
    return n


def _dates(value, what) -> list:
    if not isinstance(value, list) or len(value) > MAX_DAYS_OFF:
        raise InvalidCapacity(f"{what}: lista de fechas inválida.")
    out = set()
    for v in value:
        try:
            out.add(dt.date.fromisoformat(str(v)).isoformat())
        except ValueError:
            raise InvalidCapacity(f"{what}: fechas en formato AAAA-MM-DD.")
    return sorted(out)


def _members(cycle):
    return list(
        ProjectMember.objects.filter(project_id=cycle.project_id, is_active=True, role__gte=15, member__is_bot=False)
        .select_related("member").order_by("member__display_name")
    )


def report(cycle, today: dt.date) -> dict:
    dates = cycle_dates(cycle)
    if dates is None:
        raise InvalidCapacity("El ciclo no tiene fechas de inicio y fin.")
    start, end = dates
    cal = calendar_of(SlaPolicy.objects.filter(project_id=cycle.project_id).first())
    plan = CyclePlan.objects.filter(cycle=cycle).first()
    team_off = set(plan.team_days_off if plan else [])
    caps = {str(c.member_id): c for c in CycleCapacity.objects.filter(cycle=cycle)}
    from_day = max(today, start)

    issue_ids = list(CycleIssue.objects.filter(cycle=cycle, issue__deleted_at__isnull=True).values_list("issue_id", flat=True))
    issues = {str(i["id"]): i for i in Issue.issue_objects.filter(pk__in=issue_ids).values("id", "state__group")}
    open_ids = [i for i, v in issues.items() if v["state__group"] not in E.CLOSED_GROUPS]
    estimates = {str(e.issue_id): e for e in IssueEstimate.objects.filter(issue_id__in=open_ids)}
    done_by_issue = defaultdict(int)
    for r in Worklog.objects.filter(issue_id__in=open_ids).values("issue_id").annotate(m=Sum("duration_minutes")):
        done_by_issue[str(r["issue_id"])] = r["m"]
    assignees = defaultdict(list)
    for a in IssueAssignee.objects.filter(issue_id__in=issue_ids, deleted_at__isnull=True).values("issue_id", "assignee_id"):
        assignees[str(a["issue_id"])].append(str(a["assignee_id"]))

    work = defaultdict(float)  # minutos restantes por persona
    unestimated = defaultdict(int)
    open_count = defaultdict(int)
    unassigned = {"remaining_minutes": 0, "unestimated": 0, "count": 0}
    for iid in open_ids:
        r = E.row(estimates.get(iid), done_by_issue[iid], issues[iid]["state__group"] or "")
        who = assignees.get(iid) or []
        if not who:
            unassigned["count"] += 1
            if r["remaining_minutes"] is None:
                unassigned["unestimated"] += 1
            else:
                unassigned["remaining_minutes"] += r["remaining_minutes"]
            continue
        for m in who:
            open_count[m] += 1
            if r["remaining_minutes"] is None:
                unestimated[m] += 1
            else:
                work[m] += r["remaining_minutes"] / len(who)
    done_by_member = {
        str(r["member_id"]): r["m"]
        for r in Worklog.objects.filter(issue_id__in=issue_ids).values("member_id").annotate(m=Sum("duration_minutes"))
    }

    rows = []
    for pm in _members(cycle):
        mid = str(pm.member_id)
        cap = caps.get(mid)
        hpd = float(cap.hours_per_day) if cap else 0.0
        off = team_off | set(cap.days_off if cap else [])
        days_total = workdays(cal, start, end, off)
        days_left = workdays(cal, from_day, end, off) if from_day <= end else 0
        rows.append({
            "member_id": mid, "display_name": pm.member.display_name, "avatar_url": pm.member.avatar_url,
            "hours_per_day": hpd, "days_off": cap.days_off if cap else [],
            "days_total": days_total, "days_left": days_left,
            "capacity_minutes": round(hpd * 60 * days_total), "capacity_left_minutes": round(hpd * 60 * days_left),
            "remaining_minutes": round(work.get(mid, 0)), "unestimated": unestimated.get(mid, 0),
            "open_items": open_count.get(mid, 0), "completed_minutes": done_by_member.get(mid, 0),
        })
    return {
        "cycle": {"id": str(cycle.id), "name": cycle.name, "start": start.isoformat(), "end": end.isoformat()},
        "today": today.isoformat(),
        "team_days_off": sorted(team_off),
        "team_days_left": workdays(cal, from_day, end, team_off) if from_day <= end else 0,
        "members": rows,
        "unassigned": unassigned,
        "totals": {
            "capacity_left_minutes": sum(r["capacity_left_minutes"] for r in rows),
            "remaining_minutes": sum(r["remaining_minutes"] for r in rows) + unassigned["remaining_minutes"],
            "open_items": len(open_ids),
            "unestimated": sum(unestimated.values()) + unassigned["unestimated"],
        },
    }


def save(cycle, data, user, is_admin: bool):
    """PUT: {"team_days_off"?: [...], "members"?: [{"member_id", "hours_per_day", "days_off"}]}. Un miembro solo
    puede cambiar su propia fila; los días libres del equipo, solo un admin."""
    members = data.get("members") or []
    if not isinstance(members, list):
        raise InvalidCapacity("members debe ser una lista.")
    allowed = {str(pm.member_id) for pm in _members(cycle)}
    rows = []
    for m in members:
        mid = str((m or {}).get("member_id") or "")
        if mid not in allowed:
            raise InvalidCapacity("Alguna persona no es miembro del proyecto.")
        if not is_admin and mid != str(user.id):
            raise PermissionError
        try:
            hpd = Decimal(str(m.get("hours_per_day") or 0)).quantize(Decimal("0.01"))
        except InvalidOperation:
            raise InvalidCapacity("Horas por día: escribe un número.")
        if not Decimal(0) <= hpd <= MAX_HOURS_PER_DAY:
            raise InvalidCapacity("Horas por día: de 0 a 24.")
        rows.append((mid, hpd, _dates(m.get("days_off") or [], "Días libres")))
    team = None
    if "team_days_off" in data:
        if not is_admin:
            raise PermissionError
        team = _dates(data.get("team_days_off") or [], "Días libres del equipo")
    common = {"project_id": cycle.project_id, "workspace_id": cycle.workspace_id}
    with transaction.atomic():
        for mid, hpd, off in rows:
            CycleCapacity.objects.update_or_create(
                cycle=cycle, member_id=mid, defaults={"hours_per_day": hpd, "days_off": off, "updated_by": user, **common},
                create_defaults={"hours_per_day": hpd, "days_off": off, "created_by": user, "updated_by": user, **common},
            )
        if team is not None:
            CyclePlan.objects.update_or_create(
                cycle=cycle, defaults={"team_days_off": team, "updated_by": user, **common},
                create_defaults={"team_days_off": team, "created_by": user, "updated_by": user, **common},
            )
