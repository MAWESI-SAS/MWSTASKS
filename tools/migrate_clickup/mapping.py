# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Reglas puras ClickUp -> MWSTASKS. Sin red: se prueban solas (tests/test_mapping.py)."""
import datetime
import hashlib
import html
import re
from zoneinfo import ZoneInfo

import markdown as md

SOURCE = "clickup"
TZ = ZoneInfo("America/Bogota")
PRIORITY = {"urgent": "urgent", "high": "high", "normal": "medium", "low": "low"}
# Estados de ClickUp que significan "listo para empezar" (ni backlog ni "en curso").
UNSTARTED_HINTS = ("ready", "commited", "committed", "approved", "queue", "to do", "todo")
SPRINT_RE = re.compile(r"^sprint\b", re.I)

# Tipos de campo ClickUp -> tipo de campo MWSTASKS
FIELD_TYPES = {
    "short_text": "text", "text": "text", "email": "text", "phone": "text", "location": "text",
    "url": "url", "number": "number", "currency": "number", "emoji": "number", "date": "date",
    "checkbox": "checkbox", "drop_down": "select", "labels": "multi_select", "users": "member",
    # Relaciones con otras tareas: se guardan como texto con los nombres (Plane CE no tiene campos de relación).
    "list_relationship": "text", "tasks": "text",
}
MAX_TEXT = 2000  # igual que plane_mawesi.properties.MAX_TEXT


def clip(text: str) -> str:
    text = text.strip()
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"


def related_names(raw) -> str:
    items = raw if isinstance(raw, list) else [raw]
    return "; ".join(str(i.get("name") or i.get("id")) if isinstance(i, dict) else str(i) for i in items)


def ms_to_date(ms):
    """Milisegundos de ClickUp -> 'AAAA-MM-DD' en la hora de Colombia. None si viene vacío."""
    if ms in (None, ""):
        return None
    return datetime.datetime.fromtimestamp(int(ms) / 1000, TZ).date().isoformat()


def today() -> str:
    return datetime.datetime.now(TZ).date().isoformat()


def ms_to_iso(ms):
    if ms in (None, ""):
        return None
    return datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.timezone.utc).isoformat()


def state_group(status_type: str, name: str) -> str:
    n = name.lower()
    if status_type == "open":
        return "unstarted" if any(h in n for h in UNSTARTED_HINTS) else "backlog"
    if status_type == "done":
        return "completed"
    if status_type == "closed":
        return "cancelled" if "cancel" in n else "completed"
    return "unstarted" if any(h in n for h in UNSTARTED_HINTS) else "started"


def is_sprint(list_name: str) -> bool:
    return bool(SPRINT_RE.match(list_name.strip()))


def priority(task) -> str:
    p = (task.get("priority") or {}).get("priority")
    return PRIORITY.get(p, "none")


def md_to_html(text: str) -> str:
    """Markdown -> HTML. El HTML crudo que venga en el texto se escapa (no se interpreta)."""
    conv = md.Markdown(extensions=["extra", "sane_lists"])
    conv.preprocessors.deregister("html_block")
    conv.inlinePatterns.deregister("html")
    return conv.convert(text)


def checklists_html(checklists) -> str:
    parts = []
    for cl in checklists or []:
        items = "".join(
            f'<li data-checked="{str(bool(i.get("resolved"))).lower()}" data-type="taskItem"><p>{html.escape(i["name"])}</p></li>'
            for i in sorted(cl.get("items", []), key=lambda i: i.get("orderindex", 0))
        )
        parts.append(f"<h3>{html.escape(cl['name'])}</h3><ul data-type=\"taskList\">{items}</ul>")
    return "".join(parts)


def description_html(task) -> str:
    text = task.get("markdown_description") or task.get("text_content") or ""
    body = md_to_html(text) if text.strip() else ""
    body += checklists_html(task.get("checklists"))
    url = html.escape(task.get("url") or "")
    footer = f'<p><em>Migrado de ClickUp: <a href="{url}">{url}</a></em></p>' if url else ""
    return (body + footer) or "<p></p>"


def comment_html(comment, author: str) -> str:
    # comment[].text trae el markdown; comment_text es texto plano (sin negritas ni listas).
    text = "".join(part.get("text") or "" for part in comment.get("comment") or []) or comment.get("comment_text") or ""
    when = ms_to_date(comment.get("date")) or ""
    body = md_to_html(text) if text.strip() else "<p></p>"
    return f"<p><strong>Autor original:</strong> {html.escape(author)} — {when}</p>{body}"


def option_list(field):
    """Opciones de un campo drop_down/labels, en el formato de MWSTASKS."""
    cfg = field.get("type_config") or {}
    out = []
    for o in sorted(cfg.get("options", []), key=lambda o: o.get("orderindex", 0)):
        name = o.get("name") or o.get("label") or ""
        if name.strip():
            out.append({"name": name, "color": o.get("color") or "", "external_id": o["id"]})
    return out


def field_value(field, raw, option_ids: dict, user_ids: dict):
    """Valor ClickUp -> valor MWSTASKS. option_ids: id opción ClickUp -> id opción MWSTASKS.
    Devuelve (valor, aviso). valor=None significa "no cargar"."""
    if raw in (None, "", []):
        return None, None
    t = field["type"]
    kind = FIELD_TYPES.get(t)
    if t in ("list_relationship", "tasks"):
        return clip(related_names(raw)) or None, None
    if kind == "text":
        return clip(str(raw)) or None, None
    if kind == "url":
        v = str(raw).strip()
        return (v, None) if re.match(r"^https?://", v) else (None, f"URL inválida: {v[:60]!r}")
    if kind == "number":
        try:
            return float(raw), None
        except (TypeError, ValueError):
            return None, f"número inválido: {raw!r}"
    if kind == "date":
        return ms_to_date(raw), None
    if kind == "checkbox":
        return raw in (True, "true", 1, "1"), None
    if kind == "select":
        opts = (field.get("type_config") or {}).get("options", [])
        hit = next((o for o in opts if str(o.get("orderindex")) == str(raw) or o.get("id") == raw), None)
        mid = option_ids.get(hit["id"]) if hit else None
        return (mid, None) if mid else (None, f"opción desconocida: {raw!r}")
    if kind == "multi_select":
        ids = [option_ids[x] for x in raw if x in option_ids]
        return (ids or None), (None if len(ids) == len(raw) else "alguna opción desconocida")
    if kind == "member":
        users = raw if isinstance(raw, list) else [raw]
        ids = [user_ids.get((u.get("email") or "").lower()) for u in users if isinstance(u, dict)]
        ids = [i for i in ids if i]
        warn = "más de una persona: se guarda la primera" if len(users) > 1 else None
        return (ids[0] if ids else None), (warn if ids else "persona sin cuenta en MWSTASKS")
    return clip(str(raw)), f"tipo {t} guardado como texto"


def estimate_hours(ms):
    """Tiempo estimado de ClickUp (ms) -> horas. None si no hay o si es menor a 1 minuto (dato roto)."""
    if not ms or int(ms) < 60_000:
        return None
    return round(int(ms) / 3_600_000, 2)


LOOSE = "(sin carpeta)"


def module_name(folder: str, list_name: str) -> str:
    """Plane no tiene carpetas: el módulo lleva "Carpeta / Lista" para conservar la estructura de ClickUp."""
    name = list_name if folder == LOOSE else f"{folder} / {list_name}"
    return name.strip()[:255]


def attachment_mime(a: dict) -> str:
    """Tipo MIME del adjunto. Si falta, binario genérico (Plane lo acepta)."""
    m = (a.get("mimetype") or "").split(";")[0].strip().lower()
    return m if "/" in m else "application/octet-stream"


def attachment_name(a: dict) -> str:
    name = (a.get("title") or "").strip() or f"adjunto.{a.get('extension') or 'bin'}"
    return name[:200]


def split_minutes(total: int, cap: int = 1440):
    """Una entrada de más de 24 h se parte en trozos de como mucho `cap` minutos."""
    out = []
    while total > 0:
        out.append(min(cap, total))
        total -= cap
    return out


# ---------- copia incremental ----------
COMPARED = ("name", "state", "priority", "start_date", "target_date")
SETS = ("assignees", "labels")


def folder_of(task) -> str:
    """Nombre de la carpeta de una tarea del listado de equipo. Las listas sueltas vienen con folder.hidden=true."""
    folder = task.get("folder") or {}
    return LOOSE if folder.get("hidden") or not folder.get("name") else folder["name"]


def in_scope(task, space_id, folders) -> bool:
    """¿La tarea pertenece a este proyecto? folders vacío = todo el espacio."""
    if str((task.get("space") or {}).get("id")) != str(space_id):
        return False
    return not folders or folder_of(task) in folders


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()[:16]


def issue_changes(current: dict, wanted: dict, description_changed: bool) -> dict:
    """Campos a mandar en el PATCH: solo los que cambiaron. Plane registra un historial por cada campo que recibe."""
    diff = {k: wanted.get(k) for k in COMPARED if current.get(k) != wanted.get(k)}
    for k in SETS:
        if set(current.get(k) or []) != set(wanted.get(k) or []):
            diff[k] = wanted.get(k) or []
    if description_changed:
        # Sin binario: el editor de Plane rearma el documento desde el HTML nuevo (si no, mostraría el viejo).
        diff["description_html"] = wanted["description_html"]
        diff["description_binary"] = None
    return diff
