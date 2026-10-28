# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Documentación de toda la API (OpenAPI 3) en /api/mawesi/docs/ y /api/mawesi/docs/schema/.

- Cubre las 3 familias que acepta el token personal: la API de la web (`/api/…`), la API v1 de Plane (`/api/v1/…`) y
  las rutas MAWESI (`/api/mawesi/…` y su copia `/api/v1/mawesi/…`). Sin `/api/instances/` ni `/api/public/`.
- La arma drf-spectacular (ya viene en la imagen de Plane) mirando las vistas. Las de Plane que no declaran serializer
  salen con ruta, método y parámetros; si una vista rompe el generador, sale igual con lo mínimo (`SafeAutoSchema`).
- Las rutas MAWESI llevan descripción, permisos y ejemplos de `apidocs_catalog.py`.
- Las vistas (página y schema) están en views/apidocs.py: este módulo lo carga DRF como DEFAULT_SCHEMA_CLASS y no
  puede importar drf_spectacular.views (import circular).
"""
import re

from drf_spectacular.openapi import AutoSchema

from plane_mawesi.apidocs_catalog import CATALOG, PLANE
from plane_mawesi.tokens import DENIED, DENIED_MESSAGE

SKIP = ("/api/instances/", "/api/public/", "/api/mawesi/docs/")
FAMILIES = (
    ("/api/v1/mawesi/", "MAWESI, copia en la API v1 (misma función que `/api/mawesi/…`)."),
    ("/api/mawesi/", "MAWESI."),
    ("/api/v1/", "API v1 de Plane: estable entre versiones de Plane."),
    ("/api/", "API de la web: la misma que usa el navegador. Puede cambiar al actualizar Plane."),
)

# (expresión sobre la ruta, etiqueta). Gana la primera que coincide: lo más específico va arriba.
TAGS = [
    (r"/worklogs/", "Horas"), (r"/timer/", "Cronómetro"), (r"propert", "Campos propios"),
    (r"/types/|/issue-types/|/type/$", "Tipos de tarea"), (r"/estimate/$|/mawesi/.*/estimates/", "Estimado en horas"),
    (r"/sla/", "SLA"), (r"/templates/", "Plantillas"), (r"/recurrence/", "Repetición"),
    (r"/automations/", "Reglas automáticas"), (r"/board/|/dependencies/", "Tablero y dependencias"),
    (r"/capacity/", "Capacidad"), (r"/flow/|analytic|/dashboard", "Analítica"), (r"/code-", "Código (commits y PRs)"),
    (r"/table/", "Vista Tabla"), (r"/wiki/|/pages", "Páginas y Wiki"),
    (r"comment", "Comentarios"), (r"reaction", "Reacciones"), (r"attachment|/assets/|file-assets", "Archivos"),
    (r"issue-links|/links/", "Enlaces de tareas"), (r"relation", "Relaciones"), (r"sub-issues", "Subtareas"),
    (r"activit|histor", "Historial"), (r"/cycles", "Ciclos"), (r"/modules", "Listas (módulos)"),
    (r"/views|filters", "Vistas"), (r"/labels", "Etiquetas"), (r"/states", "Estados"), (r"intake|inbox", "Intake"),
    (r"/estimates", "Estimaciones (puntos)"), (r"notification", "Notificaciones"), (r"search", "Búsqueda"),
    (r"member|invit|join", "Miembros e invitaciones"), (r"favorite|stick|quick-link|recent|home", "Inicio y favoritos"),
    (r"/users/", "Mi usuario"), (r"/issues|/work-items|/epics", "Tareas"), (r"/projects", "Proyectos"),
    (r"/workspaces", "Workspace"),
]
TAGS = [(re.compile(rx), tag) for rx, tag in TAGS]
VERBS = {"get": "Ver", "post": "Crear", "put": "Guardar", "patch": "Cambiar", "delete": "Borrar"}


ROLE_NAMES = {20: "admins", 15: "miembros", 5: "invitados"}
WS_ADMIN_NOTE = " (y admins del workspace que están en el proyecto)"
# Clases de permiso de Plane: (para leer, para cambiar) o {método: texto}. Ver plane/app/permissions/.
PERMISSION_TEXT = {
    "ProjectEntityPermission": ("Cualquier miembro del proyecto, también invitados.", "Admins y miembros del proyecto."),
    "ProjectMemberPermission": ("Cualquier miembro del proyecto.", "Admins y miembros del proyecto."),
    "ProjectBasePermission": {"GET": "Cualquier miembro del workspace (ve sus proyectos).",
                              "POST": "Admins y miembros del workspace.", "*": "Admins del proyecto" + WS_ADMIN_NOTE + "."},
    "ProjectAdminPermission": ("Admins del proyecto.",) * 2,
    "ProjectLitePermission": ("Cualquier miembro del proyecto.",) * 2,
    "ProjectPagePermission": ("Según la página: las privadas, solo su dueño.",) * 2,
    "WorkSpaceBasePermission": {"GET": "Cualquier usuario.", "POST": "Cualquier usuario (crea un workspace).",
                                "PUT": "Admins y miembros del workspace.", "PATCH": "Admins y miembros del workspace.",
                                "DELETE": "Admins del workspace."},
    "WorkSpaceAdminPermission": ("Admins y miembros del workspace.",) * 2,
    "WorkspaceEntityPermission": ("Cualquier miembro del workspace.", "Admins y miembros del workspace."),
    "WorkspaceOwnerPermission": ("Admins del workspace.",) * 2,
    "WorkspaceViewerPermission": ("Cualquier miembro del workspace.",) * 2,
    "WorkspaceUserPermission": ("Cualquier miembro del workspace.",) * 2,
    "WorkspaceMemberPermission": ("Cualquier miembro del workspace.",) * 2,
}


def _allow_permission(fn):
    """(roles, nivel, creador) del decorador `allow_permission` de Plane sobre `fn`, o None."""
    while fn is not None:
        names = getattr(getattr(fn, "__code__", None), "co_freevars", ())
        if "allowed_roles" in names and fn.__closure__:
            cells = dict(zip(names, (c.cell_contents for c in fn.__closure__)))
            roles = [getattr(r, "value", r) for r in cells["allowed_roles"]]
            return roles, cells.get("level", "PROJECT"), bool(cells.get("creator") and cells.get("model"))
        fn = getattr(fn, "__wrapped__", None)
    return None


def who(view, method) -> str:
    """Quién puede usar la operación, leído del código de Plane (el mismo control que corre en cada pedido)."""
    action = getattr(view, "action", None) or method.lower()
    found = _allow_permission(getattr(view, action, None))
    if found:
        roles, level, creator = found
        names = [ROLE_NAMES.get(r, str(r)) for r in sorted(roles, reverse=True)]
        if not names:
            return "Solo quien lo creó." if creator else "Nadie (Plane no deja)."
        text = ", ".join(names[:-1]) + (" y " if len(names) > 1 else "") + names[-1]
        where = " del workspace" if level == "WORKSPACE" else " del proyecto" + (WS_ADMIN_NOTE if 20 not in roles else "")
        return text[0].upper() + text[1:] + where + (", o quien lo creó" if creator else "") + "."
    safe = method.upper() in ("GET", "HEAD", "OPTIONS")
    for perm in getattr(view, "permission_classes", ()):
        text = PERMISSION_TEXT.get(perm.__name__)
        if isinstance(text, dict):
            return text.get(method.upper()) or text.get("GET" if safe else "*") or text["GET"]
        if text:
            return text[0 if safe else 1]
    return "Cualquier usuario con sesión o token (cada vista filtra lo que puede ver)."


class SafeAutoSchema(AutoSchema):
    """El AutoSchema de drf-spectacular con "Quién" en cada operación. Una vista que rompe el generador no tira abajo
    toda la documentación: sale con lo mínimo."""

    def get_operation(self, *args, **kwargs):
        try:
            op = super().get_operation(*args, **kwargs)
        except Exception:  # noqa: BLE001 - p. ej. un filterset de Plane con campos que no son del modelo
            op = {"operationId": f"{self.method.lower()}{re.sub(r'[^a-zA-Z0-9]+', '_', self.path)}",
                  "responses": {"200": {"description": "OK"}}}
        if op is not None:
            try:
                op["description"] = (op.get("description", "") + f"\n\n**Quién:** {who(self.view, self.method)}").strip()
            except Exception:  # noqa: BLE001 - nunca romper la documentación por esto
                pass
        return op


def preprocess(endpoints, **kwargs):
    return [e for e in endpoints if e[0].startswith("/api/") and not e[0].startswith(SKIP)]


def _family(path):
    return next((prefix, text) for prefix, text in FAMILIES if path.startswith(prefix))


def _tag(path):
    rest = path[len(_family(path)[0]) - 1:]
    return next((tag for rx, tag in TAGS if rx.search(rest)), "Otros")


def _summary(method, path):
    last = [s for s in path.strip("/").split("/") if not s.startswith("{")][-1]
    one = path.endswith("}/")
    verb = "Ver uno" if method == "get" and one else "Listar" if method == "get" else VERBS[method]
    return f"{verb}: {last.replace('-', ' ')}"


def _apply_catalog(op, entry):
    op["summary"] = entry["summary"]
    op["description"] = entry["description"]
    params = [p for p in op.get("parameters", []) if p.get("in") != "query"]
    op["parameters"] = params + [{"in": "query", "name": n, "description": d, "required": r, "schema": {"type": "string"}}
                                 for n, d, r in entry["query"]]
    if entry["body"] is not None:
        op["requestBody"] = {"content": {"application/json": {"schema": {"type": "object"}, "example": entry["body"]}}}
    code = str(entry["status"])
    resp = {"description": "OK"}
    if entry["resp"] is not None:
        resp["content"] = {"application/json": {"schema": {}, "example": entry["resp"]}}
    op["responses"] = {code: resp, "403": {"description": "Sin permiso: el rol del dueño del token no alcanza."}}


def postprocess(result, generator, request, public):
    """Etiquetas por función, familia, seguridad y la documentación MAWESI. Corre sobre el schema ya armado."""
    for path, methods in result["paths"].items():
        prefix, family = _family(path)
        for method, op in methods.items():
            op["tags"] = [_tag(path)]
            entry = CATALOG.get((method.upper(), path[len(prefix):])) if prefix.startswith("/api/") and "mawesi" in prefix \
                else None
            plane_entry = PLANE.get((method.upper(), path[len("/api/"):])) if prefix == "/api/" else None
            if entry:
                _apply_catalog(op, entry)
            elif plane_entry:
                op["summary"] = plane_entry["summary"]
                op["description"] = "\n\n".join(x for x in (plane_entry["description"], op.get("description", "")) if x)
                if plane_entry["body"] is not None:
                    content = op.setdefault("requestBody", {}).setdefault("content", {})
                    content.setdefault("application/json", {}).setdefault("schema", {"type": "object"})
                    content["application/json"]["example"] = plane_entry["body"]
            elif not op.get("summary"):
                op["summary"] = _summary(method, path)
            notes = [f"**Familia:** {family}"]
            if any(method.upper() in methods_ and rx.match(re.sub(r"\{[^}]+\}", "x", path)) for methods_, rx in DENIED):
                notes.append(f"**Con token: no.** {DENIED_MESSAGE}")
            op["description"] = "\n\n".join([op.get("description", "")] + notes).strip()
            op["security"] = [{"Token": []}, {"Sesion": []}]
    result.setdefault("components", {})["securitySchemes"] = {
        "Token": {"type": "apiKey", "in": "header", "name": "X-Api-Key",
                  "description": "Token personal (Perfil → Personal Access Tokens). Tiene los permisos de su dueño."},
        "Sesion": {"type": "apiKey", "in": "cookie", "name": "session-id",
                   "description": "Sesión del navegador (la usa la web; con esta página abierta ya va sola)."},
    }
    return result
