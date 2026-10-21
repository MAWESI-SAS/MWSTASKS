# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Analítica de flujo de un proyecto (como los widgets de Azure DevOps):

- Flujo acumulado (CFD): cuántas tareas había en cada estado al final de cada día.
- Lead time: de creada a terminada. Cycle time: de la primera vez en un estado "started" a terminada.
- Rendimiento (throughput): tareas terminadas por semana.
- Envejecimiento: las tareas en curso que más tiempo llevan.

El estado de cada día sale del historial de Plane (IssueActivity field="state"). Una tarea sin historial se toma en su
estado actual desde que se creó; si está terminada, en el estado por defecto del proyecto hasta `completed_at`.
Las canceladas no se cuentan (como "Removed" en Azure DevOps).
"""
import datetime as dt
import math
from bisect import bisect_right
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

from django.db.models import Count, Q

from plane.db.models import Issue, IssueActivity, ModuleIssue, State

TZ = ZoneInfo("America/Bogota")
WINDOWS = (14, 30, 90, 180)
AGING_TOP = 10


def percentile(values, p):
    """Percentil con interpolación lineal (como Excel PERCENTIL.INC)."""
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def stats(days):
    if not days:
        return {"count": 0, "avg": None, "p50": None, "p85": None}
    return {"count": len(days), "avg": round(sum(days) / len(days), 1), "p50": round(percentile(days, 0.5), 1),
            "p85": round(percentile(days, 0.85), 1)}


def _days(a, b):
    return max(0.0, (b - a).total_seconds() / 86400)


def timeline(issue, changes, default_state):
    """[(desde, state_id)] en orden. `changes` = [(cuándo, old_id, new_id)] en orden."""
    if changes:
        first = changes[0][1] or issue["state_id"]
        segs = [(issue["created_at"], str(first) if first else None)]
        segs += [(when, str(new) if new else None) for when, _old, new in changes]
        return segs
    if issue["state__group"] == "completed" and issue["completed_at"]:
        return [(issue["created_at"], default_state), (issue["completed_at"], str(issue["state_id"]))]
    return [(issue["created_at"], str(issue["state_id"]))]


def analyze(project_id, days: int, now: dt.datetime, module_id=None) -> dict:
    states = list(State.objects.filter(project_id=project_id).order_by("sequence").values("id", "name", "group", "color", "default"))
    shown = [s for s in states if s["group"] != "cancelled"]
    group_of = {str(s["id"]): s["group"] for s in states}
    default_state = next((str(s["id"]) for s in states if s["default"]), str(shown[0]["id"]) if shown else None)

    today = now.astimezone(TZ).date()
    first_day = today - dt.timedelta(days=days - 1)
    start = dt.datetime.combine(first_day, dt.time.min, TZ)
    day_ends = [dt.datetime.combine(first_day + dt.timedelta(days=i), dt.time.max, TZ) for i in range(days)]

    base = Issue.issue_objects.filter(project_id=project_id).exclude(state__group="cancelled")
    if module_id:
        base = base.filter(pk__in=ModuleIssue.objects.filter(module_id=module_id, deleted_at__isnull=True).values("issue_id"))
    # Terminadas antes de la ventana: están en su estado actual todos los días (no hace falta recorrerlas).
    old_done = Q(state__group="completed", completed_at__lt=start)
    constant = Counter({str(r["state_id"]): r["n"] for r in base.filter(old_done).values("state_id").annotate(n=Count("id"))})
    active = list(base.exclude(old_done).values("id", "created_at", "completed_at", "state_id", "state__group",
                                                "sequence_id", "name", "project__identifier"))
    changes = defaultdict(list)
    for a in (IssueActivity.objects.filter(issue_id__in=[i["id"] for i in active], field="state", verb="updated")
              .order_by("created_at").values_list("issue_id", "created_at", "old_identifier", "new_identifier")):
        changes[str(a[0])].append(a[1:])

    series = {str(s["id"]): [constant.get(str(s["id"]), 0)] * days for s in shown}
    lead, cycle, throughput, aging = [], [], Counter(), []
    for issue in active:
        iid = str(issue["id"])
        segs = timeline(issue, changes[iid], default_state)
        whens = [w for w, _ in segs]
        for d, end in enumerate(day_ends):
            if end < issue["created_at"]:
                continue
            state = segs[bisect_right(whens, end) - 1][1]
            if state in series:
                series[state][d] += 1
        started_at = next((w for w, s in segs if group_of.get(s) == "started"), None)
        if issue["state__group"] == "completed" and issue["completed_at"] and issue["completed_at"] >= start:
            done = issue["completed_at"]
            lead.append(_days(issue["created_at"], done))
            if started_at and started_at <= done:
                cycle.append(_days(started_at, done))
            iso = done.astimezone(TZ).isocalendar()
            throughput[f"{iso[0]}-W{iso[1]:02d}"] += 1
        elif issue["state__group"] == "started":
            since = started_at or issue["created_at"]
            aging.append({"id": iid, "key": f"{issue['project__identifier']}-{issue['sequence_id']}", "name": issue["name"],
                          "state_id": str(issue["state_id"]), "age_days": round(_days(since, now), 1)})

    weeks, w = [], first_day - dt.timedelta(days=first_day.weekday())
    while w <= today:
        iso = w.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        weeks.append({"week": key, "start": w.isoformat(), "done": throughput.get(key, 0)})
        w += dt.timedelta(days=7)
    aging.sort(key=lambda x: -x["age_days"])
    return {
        "days": [(first_day + dt.timedelta(days=i)).isoformat() for i in range(days)],
        "states": [{"id": str(s["id"]), "name": s["name"], "group": s["group"], "color": s["color"]} for s in shown],
        "cfd": series,
        "lead_time": stats(lead),
        "cycle_time": stats(cycle),
        "cycle_time_missing": len(lead) - len(cycle),
        "throughput": weeks,
        "aging": aging[:AGING_TOP],
        "wip": sum(1 for i in active if i["state__group"] == "started"),
    }
