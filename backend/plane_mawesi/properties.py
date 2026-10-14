# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Campos propios: validación de valores por tipo, texto para el historial y guardado con historial."""
import datetime
import math
import uuid
from typing import Any, Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone

from plane.db.models import IssueActivity, ProjectMember, User

from plane_mawesi.models import OPTION_TYPES, Property, PropertyOption, PropertyType, PropertyValue

ACTIVITY_FIELD = "mawesi_property"
MAX_TEXT = 2000


class InvalidValue(ValueError):
    pass


def _uuid(v: Any) -> str:
    try:
        return str(uuid.UUID(str(v)))
    except (ValueError, TypeError, AttributeError):
        raise InvalidValue("Identificador inválido.")


def clean_value(prop: Property, raw: Any, options_by_id: dict) -> Any:
    """Valida y normaliza `raw` para el tipo del campo. Devuelve None si el valor queda vacío."""
    if raw is None or raw == "" or raw == []:
        return None
    t = prop.type
    if t == PropertyType.TEXT:
        if not isinstance(raw, str):
            raise InvalidValue("Debe ser texto.")
        v = raw.strip()
        if len(v) > MAX_TEXT:
            raise InvalidValue(f"Máximo {MAX_TEXT} caracteres.")
        return v or None
    if t == PropertyType.URL:
        if not isinstance(raw, str):
            raise InvalidValue("Debe ser una URL.")
        v = raw.strip()
        try:
            URLValidator(schemes=["http", "https"])(v)
        except DjangoValidationError:
            raise InvalidValue("URL inválida (debe empezar con http:// o https://).")
        if len(v) > MAX_TEXT:
            raise InvalidValue(f"Máximo {MAX_TEXT} caracteres.")
        return v
    if t == PropertyType.NUMBER:
        if isinstance(raw, bool):
            raise InvalidValue("Debe ser un número.")
        try:
            v = float(str(raw).replace(",", "."))
        except (TypeError, ValueError):
            raise InvalidValue("Debe ser un número.")
        if not math.isfinite(v):
            raise InvalidValue("Debe ser un número.")
        return int(v) if v.is_integer() else v
    if t == PropertyType.DATE:
        try:
            return datetime.date.fromisoformat(str(raw)).isoformat()
        except ValueError:
            raise InvalidValue("Fecha en formato AAAA-MM-DD.")
    if t == PropertyType.CHECKBOX:
        if not isinstance(raw, bool):
            raise InvalidValue("Debe ser verdadero o falso.")
        return raw
    if t == PropertyType.SELECT:
        oid = _uuid(raw)
        if oid not in options_by_id:
            raise InvalidValue("Opción inexistente.")
        return oid
    if t == PropertyType.MULTI_SELECT:
        if not isinstance(raw, list):
            raise InvalidValue("Debe ser una lista de opciones.")
        ids = list(dict.fromkeys(_uuid(x) for x in raw))
        if any(i not in options_by_id for i in ids):
            raise InvalidValue("Opción inexistente.")
        return ids or None
    if t == PropertyType.MEMBER:
        uid = _uuid(raw)
        if not ProjectMember.objects.filter(project_id=prop.project_id, member_id=uid, is_active=True).exists():
            raise InvalidValue("La persona no es miembro del proyecto.")
        return uid
    raise InvalidValue("Tipo de campo desconocido.")


def display(prop: Property, value: Any, options_by_id: dict) -> Optional[str]:
    """Texto legible del valor (para el historial). None si está vacío."""
    if value is None:
        return None
    if prop.type == PropertyType.CHECKBOX:
        return "true" if value else "false"
    if prop.type == PropertyType.SELECT:
        return options_by_id.get(value, "?")
    if prop.type == PropertyType.MULTI_SELECT:
        return ", ".join(options_by_id.get(v, "?") for v in value)
    if prop.type == PropertyType.MEMBER:
        return User.objects.filter(pk=value).values_list("display_name", flat=True).first() or "?"
    return str(value)


def option_names(prop: Property) -> dict:
    if prop.type not in OPTION_TYPES:
        return {}
    return {str(o.id): o.name for o in prop.options.all()}


def readable(prop: Property, value: Any, names: dict) -> Any:
    """Quita opciones borradas de un valor guardado antes de devolverlo."""
    if prop.type == PropertyType.SELECT:
        return value if value in names else None
    if prop.type == PropertyType.MULTI_SELECT and isinstance(value, list):
        kept = [v for v in value if v in names]
        return kept or None
    return value


def set_values(*, issue, changes: dict, actor_id) -> dict:
    """Aplica {property_id: valor|None} a un work item. Todo o nada; escribe una fila de historial por cambio.

    Lanza InvalidValue con {property_id: mensaje} si algo no valida.
    """
    props = {
        str(p.id): p
        for p in Property.objects.filter(project_id=issue.project_id, is_active=True).prefetch_related("options")
    }
    errors, cleaned = {}, {}
    for pid, raw in changes.items():
        prop = props.get(str(pid))
        if prop is None:
            errors[str(pid)] = "El campo no existe en este proyecto."
            continue
        try:
            cleaned[str(pid)] = clean_value(prop, raw, option_names(prop))
        except InvalidValue as e:
            errors[str(pid)] = str(e)
    if errors:
        raise InvalidValue(errors)

    current = {str(v.property_id): v for v in PropertyValue.objects.filter(issue=issue, property_id__in=cleaned.keys())}
    epoch = int(timezone.now().timestamp())
    activities = []
    with transaction.atomic():
        for pid, new in cleaned.items():
            prop, names = props[pid], option_names(props[pid])
            row = current.get(pid)
            old = readable(prop, row.value, names) if row else None
            if old == new:
                continue
            if new is None:
                row.delete(soft=False)
            elif row:
                row.value = new
                row.save(update_fields=["value", "updated_at", "updated_by"])
            else:
                PropertyValue.objects.create(
                    issue=issue, property=prop, value=new, project_id=issue.project_id, workspace_id=issue.workspace_id
                )
            activities.append(
                IssueActivity(
                    issue_id=issue.id,
                    project_id=issue.project_id,
                    workspace_id=issue.workspace_id,
                    actor_id=actor_id,
                    verb="updated",
                    field=ACTIVITY_FIELD,
                    old_value=display(prop, old, names),
                    new_value=display(prop, new, names),
                    new_identifier=prop.id,
                    comment=prop.name,
                    epoch=epoch,
                )
            )
        if activities:
            IssueActivity.objects.bulk_create(activities)
    return values_for_issue(issue)


def values_for_issue(issue) -> dict:
    out = {}
    rows = PropertyValue.objects.filter(issue=issue, property__is_active=True, property__deleted_at__isnull=True).select_related(
        "property"
    )
    for r in rows:
        v = readable(r.property, r.value, option_names(r.property))
        if v is not None:
            out[str(r.property_id)] = v
    return out


def upsert_options(prop: Property, options: list) -> None:
    """Sincroniza opciones: crea/actualiza las enviadas (con o sin id) y borra (soft) las que no vienen."""
    if prop.type not in OPTION_TYPES:
        return
    keep = []
    existing = {str(o.id): o for o in prop.options.all()}
    for i, o in enumerate(options):
        name = str(o.get("name", "")).strip()[:120]
        if not name:
            continue
        oid = str(o.get("id") or "")
        color = str(o.get("color", ""))[:20]
        order = o.get("sort_order", (i + 1) * 1000)
        if oid in existing:
            opt = existing[oid]
            opt.name, opt.color, opt.sort_order = name, color, order
            opt.save(update_fields=["name", "color", "sort_order", "updated_at", "updated_by"])
        else:
            opt = PropertyOption.objects.create(
                property=prop, name=name, color=color, sort_order=order,
                external_id=str(o.get("external_id", ""))[:120],
                project_id=prop.project_id, workspace_id=prop.workspace_id,
            )
        keep.append(str(opt.id))
    for oid, opt in existing.items():
        if oid not in keep:
            opt.delete()
