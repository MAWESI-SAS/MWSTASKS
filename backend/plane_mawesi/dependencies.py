# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Dependencias entre tareas que de verdad hacen algo (Plane CE solo las dibuja). Copia lo mejor de Plane pago,
ClickUp y monday:

Tipos (las relaciones que Plane ya guarda en IssueRelation):
- FS "terminar para empezar" (blocked_by / blocking): B no empieza ni termina hasta que A esté terminada.
- SS "empezar para empezar" (start_before / start_after): B no empieza hasta que A empezó.
- FF "terminar para terminar" (finish_before / finish_after): B no se termina hasta que A esté terminada.
Cancelada cuenta como resuelta (como "cerrada" en ClickUp).

Lo que hace, según la política del proyecto (DependencyPolicy; sin fila, todo prendido):
- enforce: no deja pasar una tarea a un estado "en curso" o "terminado" si algo la frena (como la advertencia de
  dependencias de ClickUp, pero sin poder saltearla). Vale para la web y la API. No frena a las integraciones de un admin
  del workspace con API key (la copia desde ClickUp manda hasta el corte).
- auto_unblock: cuando se resuelve el último bloqueo, la tarea deja una fila en el historial y, si estaba en la columna
  "Blocked", pasa sola a la primera columna "por hacer" (con el aviso de Plane a sus responsables y seguidores).
- reschedule: si un predecesor se corre y la dependiente queda chocando, la dependiente se corre lo justo, sin cambiar
  su duración (modo "flexible" de monday; se miran TODOS sus predecesores, no solo el que cambió). Nunca la adelanta.
  La cadena sigue sola: el cambio de fechas de B dispara el de sus dependientes.
- No deja crear ciclos (A espera a B y B espera a A).

Los cambios automáticos se aplican como los de Plane (su tarea `issue_activity`): quedan en el historial a nombre de
quien hizo el cambio original y avisan a los seguidores.
"""
import datetime as dt
import json
from collections import defaultdict
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from plane.app.permissions import ROLE
from plane.db.models import Issue, IssueActivity, IssueRelation, State, WorkspaceMember

from plane_mawesi.models import DependencyPolicy

FS, SS, FF = "blocked_by", "start_before", "finish_before"
KINDS = (FS, SS, FF)
# Tipo pedido por la web/API → (tipo guardado, ¿la tarea de la URL es la dependiente?)
REQUESTED = {
    "blocked_by": (FS, True), "blocking": (FS, False),
    "start_after": (SS, True), "start_before": (SS, False),
    "finish_after": (FF, True), "finish_before": (FF, False),
}
RELATION_FIELDS = set(REQUESTED)
RESOLVED = ("completed", "cancelled")
NOT_STARTED = ("backlog", "unstarted")
GUARDED = ("started", "completed")
BLOCKED_NAMES = ("blocked", "bloqueada", "bloqueado")
FIELD = "mawesi_dependency"
MARK = "mawesi-dependency"
MAX_RUNS_PER_ISSUE = 20
MAX_NODES = 5000


# ---------- grafo ----------

def _edge(r):
    """(predecesora, dependiente, tipo) de una fila de IssueRelation."""
    if r["relation_type"] == FS:
        return r["related_issue_id"], r["issue_id"], FS
    return r["issue_id"], r["related_issue_id"], r["relation_type"]


def edges_for(issue_ids):
    """Aristas de dependencia que tocan a estas tareas (sin tareas borradas)."""
    rows = IssueRelation.objects.filter(relation_type__in=KINDS).filter(
        Q(issue_id__in=issue_ids) | Q(related_issue_id__in=issue_ids)
    ).filter(issue__deleted_at__isnull=True, related_issue__deleted_at__isnull=True).values(
        "issue_id", "related_issue_id", "relation_type")
    return [_edge(r) for r in rows]


def would_cycle(workspace_id, pred_id, succ_id) -> bool:
    """¿Agregar pred → succ cierra un ciclo? (pred se alcanza desde succ siguiendo dependientes)."""
    if str(pred_id) == str(succ_id):
        return True
    nxt = defaultdict(list)
    for r in IssueRelation.objects.filter(workspace_id=workspace_id, relation_type__in=KINDS).values(
            "issue_id", "related_issue_id", "relation_type"):
        p, s, _ = _edge(r)
        nxt[str(p)].append(str(s))
    seen, stack = set(), [str(succ_id)]
    while stack and len(seen) < MAX_NODES:
        x = stack.pop()
        if x == str(pred_id):
            return True
        if x in seen:
            continue
        seen.add(x)
        stack.extend(nxt.get(x, ()))
    return False


# ---------- reglas ----------

def policy(project_id) -> DependencyPolicy:
    return DependencyPolicy.objects.filter(project_id=project_id).first() or DependencyPolicy(project_id=project_id)


def _key(i):
    return f"{i.project.identifier}-{i.sequence_id}"


def blockers(issue, target_group: str):
    """Lo que no deja pasar `issue` a un estado del grupo `target_group`: [{id, key, name, kind, state}]."""
    if target_group not in GUARDED:
        return []
    preds = [(p, k) for p, s, k in edges_for([issue.id]) if str(s) == str(issue.id)]
    if not preds:
        return []
    found = {str(i.id): i for i in Issue.issue_objects.filter(pk__in=[p for p, _ in preds]).select_related("state", "project")}
    out = []
    for pid, kind in preds:
        p = found.get(str(pid))
        if p is None:
            continue
        group = p.state.group if p.state else "backlog"
        stops = (kind == FS and group not in RESOLVED) or (kind == SS and group in NOT_STARTED) or (
            kind == FF and target_group == "completed" and group not in RESOLVED)
        if stops:
            out.append({"id": str(p.id), "key": _key(p), "name": p.name, "kind": kind, "state": p.state.name if p.state else ""})
    return out


def _short(text, size=60):
    return text if len(text) <= size else text[: size - 1].rstrip() + "…"


def message(found) -> str:
    keys = ", ".join(f"{b['key']} ({_short(b['name'])})" for b in found[:5])
    more = f" y {len(found) - 5} más" if len(found) > 5 else ""
    return f"Esta tarea está bloqueada: espera a {keys}{more}."


def guard(issue, new_state_id, user, via_api_key=False) -> Optional[list]:
    """Bloqueos que impiden el cambio de estado, o None si se puede."""
    if not new_state_id or str(new_state_id) == str(issue.state_id):
        return None
    state = State.objects.filter(pk=new_state_id, project_id=issue.project_id).first()
    if state is None or state.group not in GUARDED or not policy(issue.project_id).enforce:
        return None
    if via_api_key and WorkspaceMember.objects.filter(
            member=user, workspace_id=issue.workspace_id, role=ROLE.ADMIN.value, is_active=True).exists():
        return None  # integración de un admin (p. ej. la copia desde ClickUp): manda la otra herramienta
    return blockers(issue, state.group) or None


def date_conflicts(issues) -> set:
    """Ids de las tareas (de `issues`) cuyas fechas chocan con algún predecesor (como la línea roja de Plane pago)."""
    ids = [i.id for i in issues]
    edges = [e for e in edges_for(ids) if e[1] in set(ids)]
    if not edges:
        return set()
    preds = {i.id: i for i in Issue.issue_objects.filter(pk__in=[p for p, _, _ in edges])}
    mine = {i.id: i for i in issues}
    out = set()
    for p, s, kind in edges:
        a, b = preds.get(p), mine.get(s)
        if a is None or b is None:
            continue
        if (kind == FS and a.target_date and b.start_date and b.start_date < a.target_date) or (
                kind == SS and a.start_date and b.start_date and b.start_date < a.start_date) or (
                kind == FF and a.target_date and b.target_date and b.target_date < a.target_date):
            out.add(str(s))
    return out


# ---------- cambios automáticos ----------

def _as_text(v):
    return None if v is None else str(v)


def _apply(issue, fields: dict, actor_id):
    """Cambia la tarea y deja el historial y los avisos con la tarea `issue_activity` de Plane."""
    from plane.bgtasks.issue_activities_task import issue_activity

    current = {k: _as_text(getattr(issue, k)) for k in fields}
    if "state_id" in fields:
        issue.state_id = fields["state_id"]
        issue.save()  # Issue.save ajusta completed_at
    else:
        Issue.objects.filter(pk=issue.pk).update(**fields, updated_at=timezone.now())
    requested = {k: _as_text(v) for k, v in fields.items()}
    transaction.on_commit(lambda: issue_activity.delay(
        type="issue.activity.updated", requested_data=json.dumps(requested), current_instance=json.dumps(current),
        issue_id=str(issue.id), project_id=str(issue.project_id), actor_id=str(actor_id) if actor_id else None,
        epoch=int(timezone.now().timestamp()), notification=True, origin=settings.WEB_URL,
    ))


def _throttled(issue_id) -> bool:
    key = f"mawesi-dep:{issue_id}:{timezone.now():%Y%m%d%H%M}"
    n = cache.get_or_set(key, 0, 120)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, 120)
    return n >= MAX_RUNS_PER_ISSUE


def unblock(pred_id, actor_id) -> int:
    """La tarea `pred_id` se resolvió: avisa a sus dependientes que quedaron libres y saca de "Blocked" a las que
    estaban ahí. Devuelve cuántas quedaron libres."""
    pred = Issue.issue_objects.filter(pk=pred_id).select_related("state", "project").first()
    if pred is None or not pred.state or pred.state.group not in RESOLVED:
        return 0
    freed = 0
    succ_ids = {s for p, s, k in edges_for([pred.id]) if str(p) == str(pred.id)}
    for succ in Issue.issue_objects.filter(pk__in=succ_ids).select_related("state", "project"):
        if (succ.state and succ.state.group in RESOLVED) or blockers(succ, "started") or _throttled(succ.id):
            continue
        freed += 1
        with transaction.atomic():
            IssueActivity.objects.create(
                issue_id=succ.id, project_id=succ.project_id, workspace_id=succ.workspace_id, actor_id=actor_id,
                verb="unblocked", field=FIELD, new_value=_key(pred), new_identifier=pred.id, comment=MARK,
                epoch=int(timezone.now().timestamp()),
            )
            if policy(succ.project_id).auto_unblock and succ.state and succ.state.name.strip().lower() in BLOCKED_NAMES:
                todo = State.objects.filter(project_id=succ.project_id, group="unstarted").order_by("sequence").first()
                if todo:
                    _apply(succ, {"state_id": todo.id}, actor_id)
    return freed


def shift_needed(issue, preds) -> int:
    """Días que hay que correr `issue` para que ninguna dependencia choque (0 si no hace falta). `preds` = [(tarea, tipo)]."""
    need_start = max([p.target_date for p, k in preds if k == FS and p.target_date] +
                     [p.start_date for p, k in preds if k == SS and p.start_date], default=None)
    need_end = max([p.target_date for p, k in preds if k == FF and p.target_date], default=None)
    delta = 0
    if need_start:
        anchor = issue.start_date or issue.target_date  # sin inicio: que al menos no venza antes de poder empezar
        if anchor and anchor < need_start:
            delta = (need_start - anchor).days
    if need_end and issue.target_date and issue.target_date + dt.timedelta(days=delta) < need_end:
        delta = (need_end - issue.target_date).days
    return delta


def reschedule(pred_id, actor_id) -> int:
    """Corre las dependientes de `pred_id` que quedaron chocando. Devuelve cuántas movió."""
    succ_ids = {s for p, s, k in edges_for([pred_id]) if str(p) == str(pred_id)}
    moved = 0
    for succ in Issue.issue_objects.filter(pk__in=succ_ids).select_related("state"):
        if (succ.state and succ.state.group in RESOLVED) or not policy(succ.project_id).reschedule:
            continue
        edges = [(p, k) for p, s, k in edges_for([succ.id]) if str(s) == str(succ.id)]
        found = {i.id: i for i in Issue.issue_objects.filter(pk__in=[p for p, _ in edges])}
        delta = shift_needed(succ, [(found[p], k) for p, k in edges if p in found])
        if delta <= 0 or _throttled(succ.id):
            continue
        fields = {}
        if succ.start_date:
            fields["start_date"] = succ.start_date + dt.timedelta(days=delta)
        if succ.target_date:
            fields["target_date"] = succ.target_date + dt.timedelta(days=delta)
        with transaction.atomic():
            _apply(succ, fields, actor_id)
        moved += 1
    return moved


# ---------- disparo (lo llama automations.py con cada fila del historial) ----------

def dispatch(row):
    if row.issue_id is None or row.comment == MARK:
        return
    from plane_mawesi.tasks import run_dependencies

    issue_id, actor = str(row.issue_id), str(row.actor_id) if row.actor_id else None
    field = row.field or ""
    jobs = []
    if field == "state" and row.verb == "updated" and row.new_identifier:
        if State.objects.filter(pk=row.new_identifier, group__in=RESOLVED).exists():
            jobs.append(("unblock", issue_id))
    elif field in ("start_date", "target_date"):
        jobs.append(("reschedule", issue_id))
    elif field in RELATION_FIELDS and row.verb == "created":
        jobs.append(("reschedule", issue_id))
        if row.new_identifier:
            jobs.append(("reschedule", str(row.new_identifier)))
    if not jobs or not IssueRelation.objects.filter(relation_type__in=KINDS).filter(
            Q(issue_id=row.issue_id) | Q(related_issue_id=row.issue_id)).exists():
        return
    for job, iid in jobs:
        transaction.on_commit(lambda job=job, iid=iid: run_dependencies.delay(job, iid, actor))
