# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Las operaciones salen del schema OpenAPI del servidor (/api/mawesi/docs/schema/), no de una lista fija.

Así el CLI cubre todo lo que la API tiene hoy y lo que se agregue mañana. El schema se guarda en caché unas horas
(`--refresh` lo vuelve a pedir).
"""
import hashlib
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field

SCHEMA_PATH = "/api/mawesi/docs/schema/"
CACHE_TTL = 6 * 3600
METHODS = ("get", "post", "put", "patch", "delete")
PARAM = re.compile(r"\{([^}]+)\}")


@dataclass
class Op:
    id: str
    method: str
    path: str
    summary: str = ""
    description: str = ""
    tag: str = ""
    path_params: list = field(default_factory=list)
    query_params: list = field(default_factory=list)  # [{name, required, description}]
    body_example: object = None
    response_example: object = None

    @property
    def who(self):
        m = re.search(r"\*\*Quién:\*\*\s*(.+)", self.description)
        return m.group(1).strip() if m else ""

    @property
    def token_allowed(self):
        return "Con token: no" not in self.description

    def brief(self):
        return {"id": self.id, "method": self.method, "path": self.path, "summary": self.summary, "tag": self.tag}

    def detail(self):
        return {**self.brief(), "who": self.who, "token_allowed": self.token_allowed,
                "description": self.description, "path_params": self.path_params,
                "query_params": self.query_params, "body_example": self.body_example,
                "response_example": self.response_example}


def cache_file(url):
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "mwstasks", f"schema-{hashlib.sha1(url.encode()).hexdigest()[:12]}.json")


def load(client, refresh=False):
    path = cache_file(client.url)
    if not refresh and os.path.exists(path) and time.time() - os.path.getmtime(path) < CACHE_TTL:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    _, _, schema = client.request("GET", SCHEMA_PATH, query={"format": "json"})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(schema, f)
    os.replace(tmp, path)
    return schema


def _example(content):
    js = (content or {}).get("application/json") or next(iter((content or {}).values()), {}) or {}
    if "example" in js:
        return js["example"]
    examples = js.get("examples") or {}
    return next((e.get("value") for e in examples.values()), None)


def operations(schema):
    ops = []
    for path, item in schema.get("paths", {}).items():
        shared = item.get("parameters", [])
        for method in METHODS:
            o = item.get(method)
            if not o:
                continue
            params = shared + o.get("parameters", [])
            responses = o.get("responses", {})
            ok = next((responses[c] for c in sorted(responses) if c.startswith("2")), {})
            ops.append(Op(
                id=o.get("operationId") or f"{method}_{path}", method=method.upper(), path=path,
                summary=o.get("summary", ""), description=o.get("description", ""), tag=(o.get("tags") or [""])[0],
                path_params=PARAM.findall(path),
                query_params=[{"name": p["name"], "required": bool(p.get("required")), "description": p.get("description", "")}
                              for p in params if p.get("in") == "query"],
                body_example=_example((o.get("requestBody") or {}).get("content")),
                response_example=_example(ok.get("content")),
            ))
    return ops


def plain(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return text.lower()


# Palabras en español → cómo aparecen en las rutas y resúmenes de Plane (en inglés).
SYNONYMS = {
    "tarea": ["issue", "work-item", "work item", "workitem"], "subtarea": ["sub-issue", "sub issue"],
    "ciclo": ["cycle", "sprint"], "sprint": ["cycle"], "lista": ["module"], "modulo": ["module"],
    "carpeta": ["module"], "etiqueta": ["label"], "estado": ["state"], "comentario": ["comment"],
    "adjunto": ["attachment", "asset"], "archivo": ["asset", "attachment", "file"], "pagina": ["page"],
    "vista": ["view"], "miembro": ["member"], "persona": ["member", "user"], "usuario": ["user", "member"],
    "proyecto": ["project"], "horas": ["worklog"], "hora": ["worklog"], "relacion": ["relation"],
    "dependencia": ["relation", "blocked", "dependenc"], "enlace": ["link"], "link": ["link"],
    "invitacion": ["invit"], "notificacion": ["notification"], "aviso": ["notification"], "buscar": ["search"],
    "historial": ["history", "activit"], "actividad": ["activit"], "reaccion": ["reaction"],
    "estimacion": ["estimate"], "estimado": ["estimate"], "favorito": ["favorite"], "archivar": ["archive"],
    "archivada": ["archive"], "borrador": ["draft"], "campo": ["propert"], "valor": ["value"],
    "tipo": ["type"], "plantilla": ["template"], "regla": ["automation"], "cronometro": ["timer"],
    "analitica": ["analytic"], "intake": ["intake", "inbox"], "pegatina": ["stick"], "nota": ["stick"],
    "crear": ["post", "create", "add"], "agregar": ["post", "create", "add"], "nueva": ["post", "create"],
    "nuevo": ["post", "create"], "cambiar": ["patch", "put", "update"], "editar": ["patch", "put", "update"],
    "actualizar": ["patch", "put", "update"], "mover": ["patch", "transfer", "update"], "asignar": ["assignee", "responsable"],
    "responsable": ["assignee", "responsable"], "comentar": ["comment"], "escribir": ["description", "contenido"],
    "contenido": ["description", "contenido"], "texto": ["description", "html"], "relacionar": ["relation"],
    "bloquear": ["blocked", "dependenc"], "adjuntar": ["attachment"], "subir": ["upload", "attachment", "asset", "logo"],
    "suscribir": ["subscri"], "seguir": ["subscri"], "reaccionar": ["reaction"], "notificar": ["notification"],
    "borrar": ["delete", "destroy", "remove"], "eliminar": ["delete", "destroy", "remove"],
    "quitar": ["delete", "remove"], "listar": ["get", "list"], "ver": ["get", "retrieve", "list"],
    "leer": ["get", "retrieve"], "traer": ["get"],
}


def _variants(term):
    out = [term]
    base = term[:-1] if term.endswith("s") and len(term) > 3 else term
    for key in {term, base, base.rstrip("e") if base.endswith("es") else base}:
        out += SYNONYMS.get(key, [])
    return [plain(x) for x in out] + ([base] if base != term else [])


def search(ops, words="", tag=""):
    """Operaciones con todas las palabras (sin tildes ni mayúsculas, con sinónimos en inglés) en id, método, ruta,
    resumen, grupo o descripción. Primero las que las tienen en el resumen, después en el grupo, y las de rutas más
    cortas."""
    raw = plain(words).split()
    terms = [_variants(t) for t in raw]
    scored = []
    for op in ops:
        if tag and plain(tag) not in plain(op.tag):
            continue
        hay = plain(" ".join([op.id, op.method, op.path, op.summary, op.tag, op.description]))
        if not all(any(v in hay for v in vs) for vs in terms):
            continue
        title, summary = plain(" ".join([op.summary, op.tag, op.method, op.id])), plain(op.summary)
        # En el resumen tal cual vale 2; con un sinónimo o en el grupo, 1.
        score = sum(2 if t.rstrip("s") in summary else 1 if any(v in title for v in vs) else 0
                    for t, vs in zip(raw, terms))
        scored.append((-score, op.path.count("/"), len(op.path), op.path, op.method, op))
    return [x[-1] for x in sorted(scored, key=lambda x: x[:5])]


def find(ops, ref):
    """Por id, o por "MÉTODO /ruta" (la ruta con {parámetros}, como la muestra `mws ops`)."""
    for op in ops:
        if op.id == ref:
            return op
    parts = ref.split(None, 1)
    if len(parts) == 2:
        method, path = parts[0].upper(), parts[1]
        for op in ops:
            if op.method == method and op.path == path:
                return op
    return None
