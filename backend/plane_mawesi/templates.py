# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Plantillas de tarea: validación y aplicación. Las tareas se crean con el serializer de Plane (número, estado por
defecto, responsables, etiquetas e historial iguales a crear la tarea a mano)."""
import html
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from plane.app.serializers import IssueCreateSerializer
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import Issue, Module, ModuleIssue, Project, ProjectMember

PRIORITIES = ("urgent", "high", "medium", "low", "none")
MAX_NAME = 120
MAX_SUBTASKS = 30
MAX_CHECKLIST = 40
MAX_ITEM = 300
ISSUE_NAME_MAX = 255  # Issue.name


def checklist_html(items) -> str:
    """Mismo HTML de checklist que trajo la migración desde ClickUp (lista de tareas del editor de Plane)."""
    if not items:
        return "<p></p>"
    lis = "".join(f'<li data-checked="false" data-type="taskItem"><p>{html.escape(i)}</p></li>' for i in items)
    return f'<h3>Checklist</h3><ul data-type="taskList">{lis}</ul>'


def _clean_items(raw):
    if not isinstance(raw, list):
        raise ValueError("El checklist es una lista de textos.")
    items = [str(i).strip() for i in raw if str(i).strip()]
    if len(items) > MAX_CHECKLIST or any(len(i) > MAX_ITEM for i in items):
        raise ValueError(f"Hasta {MAX_CHECKLIST} puntos de checklist de {MAX_ITEM} letras.")
    return items


def _priority(value):
    value = value or "none"
    if value not in PRIORITIES:
        raise ValueError("Prioridad inválida.")
    return value


def parse_template(data, slug, project_id):
    """Valida el cuerpo de POST/PATCH. Devuelve (campos, error)."""
    try:
        name = str(data.get("name") or "").strip()
        if not name or len(name) > MAX_NAME:
            raise ValueError(f"El nombre va de 1 a {MAX_NAME} letras.")
        subtasks = data.get("subtasks") or []
        if not isinstance(subtasks, list) or len(subtasks) > MAX_SUBTASKS:
            raise ValueError(f"Hasta {MAX_SUBTASKS} subtareas.")
        clean_subtasks = []
        for s in subtasks:
            sname = str((s or {}).get("name") or "").strip()
            if not sname or len(sname) > MAX_NAME:
                raise ValueError(f"Cada subtarea lleva nombre (hasta {MAX_NAME} letras).")
            clean_subtasks.append({"name": sname, "priority": _priority(s.get("priority")), "checklist": _clean_items(s.get("checklist") or [])})
        assignees = data.get("assignee_ids") or []
        if not isinstance(assignees, list):
            raise ValueError("Responsables inválidos.")
        members = {str(m) for m in ProjectMember.objects.filter(
            workspace__slug=slug, project_id=project_id, member_id__in=assignees, is_active=True, role__gte=15
        ).values_list("member_id", flat=True)} if assignees else set()
        if len(members) != len(set(map(str, assignees))):
            raise ValueError("Algún responsable no es miembro del proyecto.")
        module_id = data.get("module_id") or None
        if module_id and not Module.objects.filter(pk=module_id, project_id=project_id, workspace__slug=slug).exists():
            raise ValueError("La lista no es de este proyecto.")
        fields = {
            "name": name, "priority": _priority(data.get("priority")), "module_id": module_id,
            "assignee_ids": sorted(members), "checklist": _clean_items(data.get("checklist") or []),
            "subtasks": clean_subtasks, "add_parent_name": bool(data.get("add_parent_name", True)),
        }
    except (ValueError, TypeError, AttributeError) as e:
        return None, str(e) if isinstance(e, ValueError) else "Datos inválidos."
    return fields, None


def create_issue(*, project, data, user, request_host):
    """Crea un work item como la API de Plane: su serializer (número, estado por defecto, responsables, etiquetas)
    y su tarea de historial, después del commit."""
    serializer = IssueCreateSerializer(data=data, context={
        "project_id": project.id, "workspace_id": project.workspace_id, "default_assignee_id": project.default_assignee_id,
    })
    serializer.is_valid(raise_exception=True)
    issue = serializer.save()
    if user is None:  # sin autor (p. ej. tarea repetida de alguien borrado): sin historial de creación
        return issue
    payload = json.dumps(data, cls=DjangoJSONEncoder)
    # Después del commit: si algo falla en el medio no queda historial de tareas que no existen.
    transaction.on_commit(lambda: issue_activity.delay(
        type="issue.activity.created", requested_data=payload, actor_id=str(user.id), issue_id=str(issue.id),
        project_id=str(project.id), current_instance=None, epoch=int(timezone.now().timestamp()), notification=True,
        origin=request_host,
    ))
    return issue


def _add_to_modules(issue, module_ids):
    ModuleIssue.objects.bulk_create(
        [ModuleIssue(module_id=m, issue=issue, project_id=issue.project_id, workspace_id=issue.workspace_id) for m in module_ids],
        ignore_conflicts=True,
    )


def subtask_name(template, sub, parent_name):
    name = f"{sub['name']} - {parent_name}" if template.add_parent_name else sub["name"]
    return name[:ISSUE_NAME_MAX]


@transaction.atomic
def apply(template, *, user, request_host, parent=None, name=None, module_id=None):
    """Con parent: le agrega las subtareas (no toca su descripción). Sin parent: crea la tarea `name` con prioridad,
    responsables y checklist de la plantilla, en `module_id` (o la lista de la plantilla), y sus subtareas.
    Las subtareas quedan en las mismas listas que la tarea principal. Devuelve (tarea principal, subtareas)."""
    project = Project.objects.get(pk=template.project_id)
    if parent is None:
        parent = create_issue(project=project, user=user, request_host=request_host, data={
            "name": name[:ISSUE_NAME_MAX], "priority": template.priority, "assignee_ids": template.assignee_ids,
            "description_html": checklist_html(template.checklist),
        })
        target = module_id or template.module_id
        if target:
            _add_to_modules(parent, [target])
    modules = list(ModuleIssue.objects.filter(issue=parent, deleted_at__isnull=True).values_list("module_id", flat=True))
    created = []
    # Plane lista las subtareas de la más nueva a la más vieja: se crean al revés para leerlas en el orden de la plantilla.
    for sub in reversed(template.subtasks):
        issue = create_issue(project=project, user=user, request_host=request_host, data={
            "name": subtask_name(template, sub, parent.name), "priority": sub.get("priority") or "none",
            "parent_id": str(parent.id), "description_html": checklist_html(sub.get("checklist")),
        })
        _add_to_modules(issue, modules)
        created.append(issue)
    return parent, created[::-1]


def issue_of(slug, project_id, issue_id):
    return Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk=issue_id).first()
