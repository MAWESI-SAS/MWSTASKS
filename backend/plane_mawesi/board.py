# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Configuración del tablero de un proyecto (como en Azure DevOps Boards):

- Por columna (estado): límite de tareas en curso (WIP) y definición de terminado.
- Colores de tarjeta: reglas en orden; en el navegador gana la primera que coincide.

Se guarda todo junto (PUT reemplaza la configuración entera) porque la pantalla edita todo junto.
"""
from django.db import transaction

from plane.db.models import Label, State

from plane_mawesi.models import CardRule, StateLimit

COLORS = ("red", "orange", "yellow", "green", "blue", "purple", "gray")
PRIORITIES = ("urgent", "high", "medium", "low", "none")
MAX_RULES = 20
MAX_DOD = 2000
MAX_DUE_DAYS = 90


class InvalidBoard(ValueError):
    pass


def config(project_id) -> dict:
    limits = {
        str(s.state_id): {"wip_limit": s.wip_limit, "definition_of_done": s.definition_of_done}
        for s in StateLimit.objects.filter(project_id=project_id, state__deleted_at__isnull=True)
    }
    rules = [
        {"id": str(r.id), "name": r.name, "color": r.color, "conditions": r.conditions, "enabled": r.enabled}
        for r in CardRule.objects.filter(project_id=project_id)
    ]
    return {"limits": limits, "card_rules": rules}


def _ids(value, model, project_id, what):
    ids = {str(i) for i in (value or [])}
    if ids and model.objects.filter(pk__in=ids, project_id=project_id).count() != len(ids):
        raise InvalidBoard(f"Alguna {what} no es de este proyecto.")
    return sorted(ids)


def parse_rule(raw, project_id) -> dict:
    if not isinstance(raw, dict):
        raise InvalidBoard("Regla inválida.")
    name = str(raw.get("name") or "").strip()
    if not name or len(name) > 80:
        raise InvalidBoard("Cada regla necesita un nombre de 1 a 80 letras.")
    if raw.get("color") not in COLORS:
        raise InvalidBoard(f"«{name}»: elige un color.")
    c = raw.get("conditions") or {}
    if not isinstance(c, dict):
        raise InvalidBoard(f"«{name}»: condiciones inválidas.")
    out = {}
    if c.get("priorities"):
        if any(p not in PRIORITIES for p in c["priorities"]):
            raise InvalidBoard(f"«{name}»: prioridad inválida.")
        out["priorities"] = sorted(set(c["priorities"]))
    if c.get("label_ids"):
        out["label_ids"] = _ids(c["label_ids"], Label, project_id, "etiqueta")
    if c.get("state_ids"):
        out["state_ids"] = _ids(c["state_ids"], State, project_id, "columna")
    if c.get("overdue"):
        out["overdue"] = True
    if c.get("due_in_days") not in (None, ""):
        try:
            days = int(c["due_in_days"])
        except (TypeError, ValueError):
            raise InvalidBoard(f"«{name}»: días inválidos.")
        if not 0 <= days <= MAX_DUE_DAYS:
            raise InvalidBoard(f"«{name}»: «vence en» va de 0 a {MAX_DUE_DAYS} días.")
        out["due_in_days"] = days
    if c.get("unassigned"):
        out["unassigned"] = True
    if not out:
        raise InvalidBoard(f"«{name}»: elige al menos una condición.")
    return {"name": name, "color": raw["color"], "conditions": out, "enabled": bool(raw.get("enabled", True))}


def parse_limits(raw, project_id) -> dict:
    if not isinstance(raw, dict):
        raise InvalidBoard("Límites inválidos.")
    states = set(str(s) for s in State.objects.filter(project_id=project_id).values_list("id", flat=True))
    out = {}
    for state_id, v in raw.items():
        if state_id not in states:
            raise InvalidBoard("Alguna columna no es de este proyecto.")
        v = v or {}
        limit = v.get("wip_limit")
        if limit in (None, "", 0):
            limit = None
        else:
            try:
                limit = int(limit)
            except (TypeError, ValueError):
                raise InvalidBoard("El límite es un número entero.")
            if not 1 <= limit <= 999:
                raise InvalidBoard("El límite va de 1 a 999 tareas.")
        dod = str(v.get("definition_of_done") or "").strip()
        if len(dod) > MAX_DOD:
            raise InvalidBoard(f"La definición de terminado tiene más de {MAX_DOD} letras.")
        if limit is not None or dod:
            out[state_id] = {"wip_limit": limit, "definition_of_done": dod}
    return out


def save(project, data, user) -> dict:
    limits = parse_limits(data.get("limits") or {}, project.id)
    raw_rules = data.get("card_rules") or []
    if not isinstance(raw_rules, list) or len(raw_rules) > MAX_RULES:
        raise InvalidBoard(f"Hasta {MAX_RULES} reglas de color.")
    rules = [parse_rule(r, project.id) for r in raw_rules]
    common = {"project_id": project.id, "workspace_id": project.workspace_id}
    with transaction.atomic():
        # Tablas propias, sin hijos: borrar y volver a crear es seguro (no es el .delete() en cascada de Plane).
        StateLimit.all_objects.filter(project_id=project.id).delete()
        StateLimit.objects.bulk_create([
            StateLimit(state_id=sid, created_by=user, updated_by=user, **v, **common) for sid, v in limits.items()
        ])
        CardRule.all_objects.filter(project_id=project.id).delete()
        CardRule.objects.bulk_create([
            CardRule(sort_order=i, created_by=user, updated_by=user, **r, **common) for i, r in enumerate(rules)
        ])
    return config(project.id)
