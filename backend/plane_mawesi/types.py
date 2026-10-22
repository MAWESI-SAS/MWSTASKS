# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Tipos de tarea con sus propios campos (como Jira: un Bug muestra unos campos y una Mejora otros).

- El tipo es el de Plane (db.IssueType + ProjectIssueType, columna Issue.type), así la API pública ya lo entiende.
  Ojo: nunca marcamos IssueType.is_default (Plane lo usaría al crear por API); el "por defecto del proyecto" va en
  ProjectIssueType.is_default.
- Qué campos ve cada tipo: TypeField. Qué tipo usan las tareas de una lista: ModuleType.
- Tipo efectivo de una tarea: el suyo; si no tiene, el de su lista; si no, el del proyecto; si no, ninguno (ve todos
  los campos, como antes). Así las tareas viejas y las que copia ClickUp toman el tipo de su lista sin tocarlas.
- Borrar es soft (update de deleted_at), nunca el .delete() de Plane (borra en cascada por Celery).
"""
from django.db import transaction
from django.utils import timezone

from plane.db.models import Issue, IssueActivity, IssueType, Module, ModuleIssue
from plane.db.models.issue_type import ProjectIssueType

from plane_mawesi.models import ModuleType, Property, TypeField

ACTIVITY_FIELD = "mawesi_type"
COLORS = ("gray", "red", "orange", "yellow", "green", "blue", "purple", "pink")
MAX_TYPES = 30
MAX_NAME = 80
MAX_DESCRIPTION = 500


class InvalidType(ValueError):
    pass


def project_types(project_id):
    """ProjectIssueType vivos del proyecto (sin épicas), con su IssueType."""
    return (
        ProjectIssueType.objects.filter(project_id=project_id, issue_type__deleted_at__isnull=True,
                                        issue_type__is_active=True, issue_type__is_epic=False)
        .select_related("issue_type").order_by("level", "issue_type__name")
    )


def serialize(project_id) -> list:
    links = list(project_types(project_id))
    ids = [p.issue_type_id for p in links]
    fields, modules = {}, {}
    for tf in TypeField.objects.filter(issue_type_id__in=ids, property__deleted_at__isnull=True, property__is_active=True):
        fields.setdefault(tf.issue_type_id, []).append(str(tf.property_id))
    for mt in ModuleType.objects.filter(issue_type_id__in=ids, module__deleted_at__isnull=True):
        modules.setdefault(mt.issue_type_id, []).append(str(mt.module_id))
    return [
        {
            "id": str(p.issue_type_id), "name": p.issue_type.name, "description": p.issue_type.description,
            "color": (p.issue_type.logo_props or {}).get("color", "gray"), "is_default": p.is_default,
            "property_ids": fields.get(p.issue_type_id, []), "module_ids": sorted(modules.get(p.issue_type_id, [])),
        }
        for p in links
    ]


def _ids(raw, model, project_id, what) -> list:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise InvalidType(f"Lista de {what} inválida.")
    ids = list(dict.fromkeys(str(i) for i in raw))  # sin repetidos, en el orden pedido
    filters = {"pk__in": ids, "project_id": project_id}
    if model is Property:
        filters["is_active"] = True
    try:
        found = model.objects.filter(**filters).count()
    except Exception:  # noqa: BLE001 - ids mal formados
        raise InvalidType(f"Algún {what} no es de este proyecto.")
    if found != len(ids):
        raise InvalidType(f"Algún {what} no es de este proyecto.")
    return ids


def parse(project_id, data, current=None) -> dict:
    name = str(data.get("name", current.name if current else "") or "").strip()
    if not name or len(name) > MAX_NAME:
        raise InvalidType(f"El nombre va de 1 a {MAX_NAME} letras.")
    taken = project_types(project_id).filter(issue_type__name__iexact=name)
    if current:
        taken = taken.exclude(issue_type_id=current.id)
    if taken.exists():
        raise InvalidType("Ya hay un tipo con ese nombre en el proyecto.")
    color = data.get("color") or ((current.logo_props or {}).get("color") if current else None) or "gray"
    if color not in COLORS:
        raise InvalidType("Elige un color.")
    description = str(data.get("description", current.description if current else "") or "").strip()
    if len(description) > MAX_DESCRIPTION:
        raise InvalidType(f"La descripción tiene más de {MAX_DESCRIPTION} letras.")
    out = {"name": name, "color": color, "description": description}
    if "property_ids" in data:
        out["property_ids"] = _ids(data["property_ids"], Property, project_id, "campo")
    if "module_ids" in data:
        out["module_ids"] = _ids(data["module_ids"], Module, project_id, "lista")
    if "is_default" in data:
        out["is_default"] = bool(data["is_default"])
    return out


def _set_fields(project, issue_type, property_ids, user):
    now = timezone.now()
    live = {str(tf.property_id): tf for tf in TypeField.objects.filter(issue_type=issue_type)}
    TypeField.objects.filter(issue_type=issue_type).exclude(property_id__in=property_ids).update(deleted_at=now)
    for i, pid in enumerate(property_ids):
        order = (i + 1) * 1000
        if pid in live:
            if live[pid].sort_order != order:
                TypeField.objects.filter(pk=live[pid].pk).update(sort_order=order)
        else:
            TypeField.objects.create(issue_type=issue_type, property_id=pid, sort_order=order, project=project,
                                     workspace_id=project.workspace_id, created_by=user, updated_by=user)


def _set_modules(project, issue_type, module_ids, user):
    now = timezone.now()
    ModuleType.objects.filter(issue_type=issue_type).exclude(module_id__in=module_ids).update(deleted_at=now)
    # Una lista tiene un solo tipo: si estaba en otro, se mueve a este.
    ModuleType.objects.filter(module_id__in=module_ids).exclude(issue_type=issue_type).update(deleted_at=now)
    have = set(str(m) for m in ModuleType.objects.filter(issue_type=issue_type).values_list("module_id", flat=True))
    for mid in module_ids:
        if mid not in have:
            ModuleType.objects.create(module_id=mid, issue_type=issue_type, project=project,
                                      workspace_id=project.workspace_id, created_by=user, updated_by=user)


def save(project, data, user, issue_type=None):
    """Crea (issue_type=None) o edita un tipo del proyecto. Devuelve el IssueType."""
    if issue_type is None and project_types(project.id).count() >= MAX_TYPES:
        raise InvalidType(f"Hasta {MAX_TYPES} tipos por proyecto.")
    v = parse(project.id, data, issue_type)
    with transaction.atomic():
        if issue_type is None:
            issue_type = IssueType.objects.create(
                workspace_id=project.workspace_id, name=v["name"], description=v["description"],
                logo_props={"color": v["color"]}, created_by=user, updated_by=user)
            ProjectIssueType.objects.create(project=project, workspace_id=project.workspace_id, issue_type=issue_type,
                                            level=project_types(project.id).count(), created_by=user, updated_by=user)
        else:
            IssueType.objects.filter(pk=issue_type.pk).update(
                name=v["name"], description=v["description"],
                logo_props={**(issue_type.logo_props or {}), "color": v["color"]}, updated_by=user)
        if "is_default" in v:
            links = ProjectIssueType.objects.filter(project_id=project.id)
            if v["is_default"]:
                links.exclude(issue_type=issue_type).update(is_default=False)
            links.filter(issue_type=issue_type).update(is_default=v["is_default"])
        if "property_ids" in v:
            _set_fields(project, issue_type, v["property_ids"], user)
        if "module_ids" in v:
            _set_modules(project, issue_type, v["module_ids"], user)
    return issue_type


def remove(project, issue_type):
    """Las tareas de este tipo vuelven al tipo de su lista (o a ninguno); sus valores no se tocan."""
    now = timezone.now()
    with transaction.atomic():
        Issue.all_objects.filter(project_id=project.id, type=issue_type).update(type=None)
        TypeField.objects.filter(issue_type=issue_type).update(deleted_at=now)
        ModuleType.objects.filter(issue_type=issue_type).update(deleted_at=now)
        ProjectIssueType.objects.filter(issue_type=issue_type).update(deleted_at=now)
        if not ProjectIssueType.objects.filter(issue_type=issue_type).exists():
            IssueType.objects.filter(pk=issue_type.pk).update(deleted_at=now)


def get_type(project_id, type_id):
    try:
        return project_types(project_id).filter(issue_type_id=type_id).first()
    except Exception:  # noqa: BLE001 - id mal formado
        return None


def effective(project_id, issues) -> dict:
    """{issue_id: {"type_id", "source"}} con source "issue" | "list" | "project" | None."""
    links = list(project_types(project_id))
    valid = {p.issue_type_id for p in links}
    default = next((p.issue_type_id for p in links if p.is_default), None)
    out, pending = {}, []
    for i in issues:
        if i.type_id in valid:
            out[str(i.id)] = {"type_id": str(i.type_id), "source": "issue"}
        else:
            pending.append(i.id)
    if pending:
        by_module = dict(ModuleType.objects.filter(project_id=project_id, issue_type_id__in=valid,
                                                   module__deleted_at__isnull=True).values_list("module_id", "issue_type_id"))
        first = {}
        if by_module:
            rows = (ModuleIssue.objects.filter(issue_id__in=pending, module_id__in=by_module.keys(), deleted_at__isnull=True)
                    .order_by("created_at").values_list("issue_id", "module_id"))
            for iid, mid in rows:
                first.setdefault(iid, by_module[mid])
        for iid in pending:
            if iid in first:
                out[str(iid)] = {"type_id": str(first[iid]), "source": "list"}
            elif default:
                out[str(iid)] = {"type_id": str(default), "source": "project"}
            else:
                out[str(iid)] = {"type_id": None, "source": None}
    return out


def set_issue_type(issue, type_id, actor_id):
    """type_id=None vuelve a "automático" (el de la lista). Deja una fila en el historial si cambia el tipo efectivo."""
    new = None
    if type_id:
        link = get_type(issue.project_id, type_id)
        if link is None:
            raise InvalidType("Ese tipo no es de este proyecto.")
        new = link.issue_type_id
    if issue.type_id == new:
        return
    before = effective(issue.project_id, [issue])[str(issue.id)]["type_id"]
    with transaction.atomic():
        Issue.all_objects.filter(pk=issue.pk).update(type_id=new)
        issue.type_id = new
        after = effective(issue.project_id, [issue])[str(issue.id)]["type_id"]
        if before != after:
            names = {str(k): v for k, v in IssueType.all_objects.filter(pk__in=[x for x in (before, after) if x]).values_list("id", "name")}
            name = lambda x: names.get(str(x)) if x else None  # noqa: E731
            IssueActivity.objects.create(
                issue_id=issue.id, project_id=issue.project_id, workspace_id=issue.workspace_id, actor_id=actor_id,
                verb="updated", field=ACTIVITY_FIELD, old_value=name(before), new_value=name(after),
                comment="updated work item type", epoch=int(timezone.now().timestamp()),
            )


def visible_property_ids(type_id):
    """Ids de los campos que muestra el tipo, en su orden; None = todos (tarea sin tipo)."""
    if not type_id:
        return None
    return [str(p) for p in TypeField.objects.filter(issue_type_id=type_id).values_list("property_id", flat=True)]
