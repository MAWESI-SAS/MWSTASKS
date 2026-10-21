# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Reglas automáticas por proyecto: "Cuando <algo pasa> → <acciones>".

Disparo: cada fila nueva del historial de Plane (IssueActivity) que sea "se creó", "entró a una lista", "cambió el
estado" o "cambió la prioridad" encola run_automations (Celery) después del commit. Así da igual si el cambio vino de
la web, del tablero o de la API. Plane escribe el historial con bulk_create dentro de su tarea `issue_activity` (no
hay post_save): se leen las filas que dejó esa tarea al terminar (task_prerun/task_postrun). Las filas creadas de a
una (p. ej. "entró a la lista" de una plantilla) llegan por post_save.

Las acciones se aplican con el ORM y dejan su propia fila de historial marcada con MARK: esas filas NO disparan
reglas (una regla no puede encadenar otra ni a sí misma). Además, tope de MAX_RUNS_PER_ISSUE por tarea y minuto.
"""
import datetime as dt

from crum import impersonate
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from plane.db.models import (
    Issue, IssueActivity, IssueAssignee, IssueLabel, Label, Module, ProjectMember, State,
)

from plane_mawesi import dependencies
from plane_mawesi import recurrence as R
from plane_mawesi import templates as T
from plane_mawesi.models import Automation, AutomationTrigger, TaskTemplate

MARK = "mawesi-automation"
MAX_RUNS_PER_ISSUE = 20
MAX_DUE_DAYS = 365
PRIORITIES = T.PRIORITIES


# ---------- validación ----------

def parse_rule(data, slug, project_id):
    """Valida el cuerpo de POST/PATCH. Devuelve (campos, error)."""
    in_project = {"workspace__slug": slug, "project_id": project_id}
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 120:
        return None, "El nombre va de 1 a 120 letras."
    trigger = data.get("trigger")
    if trigger not in AutomationTrigger.values:
        return None, "Elige cuándo se dispara."
    value = str(data.get("trigger_value") or "")
    if trigger == AutomationTrigger.CREATED:
        value = ""
    elif trigger == AutomationTrigger.PRIORITY and value not in PRIORITIES:
        return None, "Elige la prioridad."
    elif trigger == AutomationTrigger.STATE and not State.objects.filter(pk=value or None, **in_project).exists():
        return None, "Elige el estado."
    elif trigger == AutomationTrigger.ADDED_TO_LIST and not Module.objects.filter(pk=value or None, **in_project).exists():
        return None, "Elige la lista."
    module_id = data.get("module_id") or None
    if trigger not in (AutomationTrigger.STATE, AutomationTrigger.PRIORITY):
        module_id = None
    if module_id and not Module.objects.filter(pk=module_id, **in_project).exists():
        return None, "La lista no es de este proyecto."

    raw = data.get("actions") or {}
    if not isinstance(raw, dict):
        return None, "Acciones inválidas."
    actions = {}
    try:
        if raw.get("assignee_ids"):
            ids = {str(i) for i in raw["assignee_ids"]}
            ok = {str(m) for m in ProjectMember.objects.filter(member_id__in=ids, is_active=True, role__gte=15, **in_project)
                  .values_list("member_id", flat=True)}
            if ok != ids:
                return None, "Algún responsable no es miembro del proyecto."
            actions["assignee_ids"] = sorted(ids)
        if raw.get("state_id"):
            if not State.objects.filter(pk=raw["state_id"], **in_project).exists():
                return None, "El estado no es de este proyecto."
            actions["state_id"] = str(raw["state_id"])
        if raw.get("priority"):
            if raw["priority"] not in PRIORITIES:
                return None, "Prioridad inválida."
            actions["priority"] = raw["priority"]
        if raw.get("label_ids"):
            ids = {str(i) for i in raw["label_ids"]}
            if Label.objects.filter(pk__in=ids, **in_project).count() != len(ids):
                return None, "Alguna etiqueta no es de este proyecto."
            actions["label_ids"] = sorted(ids)
        if raw.get("due_in_days") not in (None, ""):
            days = int(raw["due_in_days"])
            if not 0 <= days <= MAX_DUE_DAYS:
                return None, f"El vencimiento va de 0 a {MAX_DUE_DAYS} días hábiles."
            actions["due_in_days"] = days
        if raw.get("template_id"):
            if not TaskTemplate.objects.filter(pk=raw["template_id"], **in_project).exclude(subtasks=[]).exists():
                return None, "La plantilla no existe o no tiene subtareas."
            actions["template_id"] = str(raw["template_id"])
    except (TypeError, ValueError):
        return None, "Acciones inválidas."
    if not actions:
        return None, "Elige al menos una acción."
    if trigger == AutomationTrigger.STATE and actions.get("state_id") == value:
        return None, "La acción no puede volver a poner el mismo estado."
    return {"name": name, "enabled": bool(data.get("enabled", True)), "trigger": trigger, "trigger_value": value,
            "module_id": module_id, "actions": actions}, None


# ---------- disparo ----------

def event_of(activity):
    """(trigger, valor) de una fila del historial, o None si no dispara reglas."""
    if activity.comment == MARK:
        return None
    if activity.field is None and activity.verb == "created":
        return AutomationTrigger.CREATED, ""
    if activity.field == "modules" and activity.verb == "created" and activity.new_identifier:
        return AutomationTrigger.ADDED_TO_LIST, str(activity.new_identifier)
    if activity.field == "state" and activity.verb == "updated" and activity.new_identifier:
        return AutomationTrigger.STATE, str(activity.new_identifier)
    if activity.field == "priority" and activity.verb == "updated" and activity.new_value:
        return AutomationTrigger.PRIORITY, activity.new_value
    return None


ISSUE_ACTIVITY_TASK = "plane.bgtasks.issue_activities_task.issue_activity"
_started = {}  # task_id → inicio, por proceso del worker


def on_task_prerun(sender=None, task_id=None, task=None, **kwargs):
    if task is not None and task.name == ISSUE_ACTIVITY_TASK:
        _started[task_id] = timezone.now()


def on_task_postrun(sender=None, task_id=None, task=None, kwargs=None, state=None, **extra):
    start = _started.pop(task_id, None)
    issue_id = (kwargs or {}).get("issue_id")
    if start is None or state != "SUCCESS" or not issue_id:
        return
    for row in IssueActivity.objects.filter(issue_id=issue_id, created_at__gte=start).exclude(comment=MARK):
        dispatch(row)


def on_activity(sender, instance, created, **kwargs):
    """post_save de IssueActivity (filas creadas de a una)."""
    if created:
        dispatch(instance)


def dispatch(instance):
    """Barato: solo encola si hay reglas activas que coinciden. Cada fila pasa también por las dependencias
    (dependencies.dispatch): mismo disparo, otra lógica."""
    if instance.issue_id is None:
        return
    dependencies.dispatch(instance)
    event = event_of(instance)
    if event is None:
        return
    trigger, value = event
    rules = Automation.objects.filter(project_id=instance.project_id, enabled=True, trigger=trigger)
    if trigger != AutomationTrigger.CREATED:
        rules = rules.filter(trigger_value=value)
    if not rules.exists():
        return
    from plane_mawesi.tasks import run_automations

    issue_id, project_id = str(instance.issue_id), str(instance.project_id)
    transaction.on_commit(lambda: run_automations.delay(issue_id, project_id, trigger, value))


# ---------- ejecución ----------

def _record(issue, actor_id, field, old_value, new_value, old_id=None, new_id=None):
    IssueActivity.objects.create(
        issue_id=issue.id, project_id=issue.project_id, workspace_id=issue.workspace_id, actor_id=actor_id,
        verb="updated", field=field, old_value=old_value, new_value=new_value, old_identifier=old_id,
        new_identifier=new_id, comment=MARK, epoch=int(timezone.now().timestamp()),
    )


def _apply(rule, issue):
    a, actor = rule.actions, rule.created_by_id
    pid, wid = issue.project_id, issue.workspace_id
    if a.get("state_id") and str(issue.state_id) != a["state_id"]:
        new = State.objects.filter(pk=a["state_id"]).first()
        # Una regla no puede saltarse una dependencia (las mismas reglas que la web y la API).
        if new and not dependencies.guard(issue, new.id, rule.created_by):
            old = issue.state
            issue.state = new
            issue.save()  # Issue.save ajusta completed_at
            _record(issue, actor, "state", old.name if old else None, new.name, old.id if old else None, new.id)
    if a.get("priority") and issue.priority != a["priority"]:
        old = issue.priority
        Issue.objects.filter(pk=issue.pk).update(priority=a["priority"], updated_at=timezone.now())
        issue.priority = a["priority"]
        _record(issue, actor, "priority", old, a["priority"])
    for uid in a.get("assignee_ids", []):
        if not IssueAssignee.objects.filter(issue=issue, assignee_id=uid).exists():
            IssueAssignee.objects.create(issue=issue, assignee_id=uid, project_id=pid, workspace_id=wid)
            member = IssueAssignee.objects.filter(issue=issue, assignee_id=uid).select_related("assignee").first()
            _record(issue, actor, "assignees", "", member.assignee.display_name, None, uid)
    for lid in a.get("label_ids", []):
        if not IssueLabel.objects.filter(issue=issue, label_id=lid).exists():
            label = IssueLabel.objects.create(issue=issue, label_id=lid, project_id=pid, workspace_id=wid).label
            _record(issue, actor, "labels", "", label.name, None, lid)
    if a.get("due_in_days") is not None:
        due = today_plus_weekdays(a["due_in_days"])
        if issue.target_date != due and not (issue.start_date and issue.start_date > due):
            old = issue.target_date
            Issue.objects.filter(pk=issue.pk).update(target_date=due, updated_at=timezone.now())
            issue.target_date = due
            _record(issue, actor, "target_date", old.isoformat() if old else None, due.isoformat())
    if a.get("template_id"):
        template = TaskTemplate.objects.filter(pk=a["template_id"]).first()
        if template and template.subtasks:
            T.apply(template, user=rule.created_by, request_host=settings.WEB_URL, parent=issue)


def matches(rule, issue) -> bool:
    if rule.trigger == AutomationTrigger.CREATED and issue.parent_id:
        return False  # subtareas (p. ej. las de una plantilla): no, para no aplicar reglas en cadena
    if rule.module_id and not issue.issue_module.filter(module_id=rule.module_id, deleted_at__isnull=True).exists():
        return False
    return True


def run(issue_id, project_id, trigger, value) -> int:
    """Aplica las reglas activas que coinciden. Devuelve cuántas corrieron."""
    key = f"mawesi-auto:{issue_id}:{timezone.now():%Y%m%d%H%M}"
    if cache.get_or_set(key, 0, 120) >= MAX_RUNS_PER_ISSUE:
        return 0
    rules = Automation.objects.filter(project_id=project_id, enabled=True, trigger=trigger).select_related("created_by")
    if trigger != AutomationTrigger.CREATED:
        rules = rules.filter(trigger_value=value)
    done = 0
    for rule in rules:
        with transaction.atomic():
            issue = Issue.issue_objects.select_for_update(of=("self",)).filter(pk=issue_id).select_related("state").first()
            if issue is None or not matches(rule, issue):
                continue
            with impersonate(rule.created_by):
                _apply(rule, issue)
            Automation.objects.filter(pk=rule.pk).update(runs=F("runs") + 1, last_run_at=timezone.now())
        done += 1
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, 120)
    return done


def today_plus_weekdays(days: int) -> dt.date:
    return R.step(R.today(), "weekdays", days) if days else R.today()
