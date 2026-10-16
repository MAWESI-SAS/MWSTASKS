# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""SLA: plazo en horas hábiles por prioridad y tiempo en cada estado (Plane CE no lo trae).

Horas hábiles: días laborales de la política, dentro de su horario, en su zona horaria, sin festivos de Colombia
(si la política lo pide). El reloj arranca al crear el work item y para al pasar a un estado "completed";
los "cancelled" no tienen SLA.
"""
import datetime as dt
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

PRIORITIES = ("urgent", "high", "medium", "low", "none")
DEFAULT_HOURS = {"urgent": 4, "high": 8, "medium": 16, "low": 40, "none": 40}
AT_RISK_SHARE = 0.25  # "en riesgo" cuando queda el 25 % del plazo o menos
MAX_DAYS = 3650  # tope de seguridad para no iterar sin fin


# --- Festivos de Colombia (Ley 51 de 1983 "Emiliani" + fechas de Pascua) ---

def easter(year: int) -> dt.date:
    """Domingo de Pascua (algoritmo gregoriano anónimo)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return dt.date(year, month, day)


def _next_monday(d: dt.date) -> dt.date:
    return d + dt.timedelta(days=(7 - d.weekday()) % 7)


@lru_cache(maxsize=64)
def colombia_holidays(year: int) -> frozenset:
    fixed = [(1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25)]
    moved = [(1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11)]
    e = easter(year)
    days = {dt.date(year, m, d) for m, d in fixed}
    days |= {_next_monday(dt.date(year, m, d)) for m, d in moved}
    days |= {e - dt.timedelta(days=3), e - dt.timedelta(days=2)}  # jueves y viernes santo
    days |= {_next_monday(e + dt.timedelta(days=n)) for n in (39, 60, 68)}  # Ascensión, Corpus, Sagrado Corazón
    return frozenset(days)


# --- Calendario hábil ---

@dataclass(frozen=True)
class Calendar:
    tz: str = "America/Bogota"
    start: dt.time = dt.time(8, 0)
    end: dt.time = dt.time(18, 0)
    workdays: tuple = (0, 1, 2, 3, 4)  # lunes=0
    holidays: bool = True

    def is_workday(self, d: dt.date) -> bool:
        return d.weekday() in self.workdays and not (self.holidays and d in colombia_holidays(d.year))

    def _window(self, d: dt.date):
        zone = ZoneInfo(self.tz)
        return dt.datetime.combine(d, self.start, zone), dt.datetime.combine(d, self.end, zone)

    def add_minutes(self, start: dt.datetime, minutes: int) -> dt.datetime:
        """Momento en que se cumplen `minutes` minutos hábiles contando desde `start`."""
        cur = start.astimezone(ZoneInfo(self.tz))
        left = minutes
        for _ in range(MAX_DAYS):
            day = cur.date()
            if self.is_workday(day):
                open_, close = self._window(day)
                begin = max(cur, open_)
                if begin < close:
                    avail = (close - begin).total_seconds() / 60
                    if left <= avail:
                        return begin + dt.timedelta(minutes=left)
                    left -= avail
            cur = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0), ZoneInfo(self.tz))
        raise ValueError("plazo fuera de rango")

    def minutes_between(self, a: dt.datetime, b: dt.datetime) -> int:
        """Minutos hábiles entre a y b (0 si b <= a)."""
        if b <= a:
            return 0
        zone = ZoneInfo(self.tz)
        a, b = a.astimezone(zone), b.astimezone(zone)
        total, day = 0.0, a.date()
        for _ in range(MAX_DAYS):
            if day > b.date():
                break
            if self.is_workday(day):
                open_, close = self._window(day)
                lo, hi = max(a, open_), min(b, close)
                if hi > lo:
                    total += (hi - lo).total_seconds() / 60
            day += dt.timedelta(days=1)
        return int(round(total))


# --- SLA de un work item ---

def sla_for(*, created_at: dt.datetime, priority: str, hours: dict, state_group: str,
            completed_at: Optional[dt.datetime], cal: Calendar, now: dt.datetime) -> dict:
    target = int(round(float(hours.get(priority or "none", hours.get("none", 0))) * 60))
    due_at = cal.add_minutes(created_at, target)
    if state_group == "cancelled":
        return {"status": "cancelled", "due_at": due_at, "target_minutes": target, "elapsed_minutes": None,
                "remaining_minutes": None}
    done = state_group == "completed"
    end = (completed_at or now) if done else now
    elapsed = cal.minutes_between(created_at, end)
    remaining = target - elapsed
    if done:
        status = "met" if remaining >= 0 else "missed"
    elif remaining < 0:
        status = "breached"
    elif remaining <= target * AT_RISK_SHARE:
        status = "at_risk"
    else:
        status = "on_track"
    return {"status": status, "due_at": due_at, "target_minutes": target, "elapsed_minutes": elapsed,
            "remaining_minutes": remaining}


def time_in_states(*, created_at: dt.datetime, current_state: str, changes: Iterable[tuple], now: dt.datetime,
                   cal: Calendar) -> list:
    """Tiempo en cada estado. `changes` = [(cuándo, estado_anterior, estado_nuevo)] en orden.

    Devuelve [{state, minutes, business_minutes, visits}] en el orden en que aparecieron los estados.
    """
    changes = list(changes)
    segments, since = [], created_at
    state = changes[0][1] if changes else current_state
    for when, old, new in changes:
        segments.append((state or old, since, when))
        state, since = new, when
    segments.append((state, since, now))
    out = {}
    for name, a, b in segments:
        row = out.setdefault(name or "?", {"state": name or "?", "minutes": 0, "business_minutes": 0, "visits": 0})
        row["minutes"] += max(0, int((b - a).total_seconds() // 60))
        row["business_minutes"] += cal.minutes_between(a, b)
        row["visits"] += 1
    return list(out.values())
