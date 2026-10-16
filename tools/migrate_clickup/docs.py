# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Docs de ClickUp -> paquete listo para cargar como Páginas de MWSTASKS (con `pages_shell.py`).

ClickUp es SOLO LECTURA. La API v1 de Plane no tiene Páginas; por eso esto arma un paquete en disco
(`pages.json` + `images/`) y la carga va por el shell del contenedor api.

  CLICKUP_TOKEN=... python -m tools.migrate_clickup.docs --config sync.json --out <carpeta>

Reglas:
- Un doc = una Página. Sus sub-páginas van como secciones (Plane CE no anida páginas; el panel de
  "Contenido" de la Página muestra los títulos como índice).
- Destino: el proyecto del espacio de ClickUp donde vive el doc (según `--config`); si cuelga de una tarea,
  el proyecto de esa tarea (y la tarea recibe un link a la Página). Lo demás va a `--default-project`.
- No se copian docs vacíos ni las plantillas de ejemplo de ClickUp.
- Las imágenes y archivos alojados en ClickUp se bajan (al cancelar ClickUp dejarían de verse).
"""
import argparse
import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone

from .clickup import ClickUp
from . import mapping as M

V3 = "https://api.clickup.com/api/v3"
# Tipos de "padre" de un doc en la API v3 de ClickUp.
TASK, SPACE, FOLDER, LIST, WORKSPACE = 1, 4, 5, 6, 12
TEMPLATES = {"getting started guide", "start here", "start here!", "how to use this template", "about this template"}
MIN_CHARS = 50
CLICKUP_FILE = re.compile(r"https://t\d+\.p\.clickup-attachments\.com/\S+")
BR = re.compile(r"<br\s*/?>", re.I)
BR_MARK = "\u0000BR\u0000"
# "Tarjeta de link" de ClickUp: [\n\ntítulo\n\nurl\n\n](url). Markdown no la entiende (el texto del link tiene saltos).
BOOKMARK = re.compile(r"\[\s*\n([^\]]*?)\]\((\S+?)\)")


def walk(pages):
    for p in pages or []:
        yield p, 0
        for child, depth in walk(p.get("pages")):
            yield child, depth + 1


def page_md(p) -> str:
    return (p.get("content") or "").strip()


def is_skipped(name: str, pages) -> str | None:
    """Motivo para no copiar el doc, o None."""
    if name.strip().lower() in TEMPLATES:
        return "plantilla de ClickUp"
    if sum(len(page_md(p)) for p, _ in walk(pages)) < MIN_CHARS:
        return "vacío"
    return None


def bookmark(m) -> str:
    lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
    return f"[{lines[0] if lines else m.group(2)}]({m.group(2)})"


def to_html(text: str) -> str:
    """Markdown de ClickUp -> HTML. Respeta los <br> (ClickUp los usa en tablas) y las tarjetas de link;
    el resto del HTML crudo se escapa."""
    return M.md_to_html(BR.sub(BR_MARK, BOOKMARK.sub(bookmark, text))).replace(html.escape(BR_MARK), "<br>").replace(BR_MARK, "<br>")


def doc_html(pages) -> str:
    """Una Página con todas las sub-páginas: la primera es el cuerpo; cada sub-página, una sección con su título."""
    parts = []
    for i, (p, depth) in enumerate(walk(pages)):
        body = page_md(p)
        if i > 0:
            level = min(1 + depth, 3)
            parts.append(f"<h{level}>{html.escape(p.get('name') or '')}</h{level}>")
        if body:
            parts.append(to_html(body))
    return "".join(parts) or "<p></p>"


def image_name(url: str) -> str:
    """Nombre estable y único por URL (el mismo archivo no se baja dos veces)."""
    base = re.sub(r"[^\w.-]", "_", url.split("?")[0].rsplit("/", 1)[-1])[-80:] or "imagen"
    return f"{hashlib.sha1(url.encode()).hexdigest()[:12]}-{base}"


def localize(body: str, out_dir: str, cu: ClickUp, max_bytes: int, warn) -> str:
    """Baja las imágenes (`<img src>`) y archivos (`<a href>`) alojados en ClickUp y los marca con
    `data-mawesi-img` / `data-mawesi-file` + el archivo local; pages_shell.py los sube a MWSTASKS."""
    def fetch(url: str) -> str | None:
        name = image_name(url)
        path = os.path.join(out_dir, "images", name)
        if not os.path.exists(path):
            try:
                data = cu.download(url, max_bytes)
            except Exception as e:  # noqa: BLE001 - se avisa y se deja el link original
                warn(f"no copiado: {url[:80]} ({e})")
                return None
            with open(path, "wb") as f:
                f.write(data)
        return name

    def swap(mark):
        def inner(m):
            url = html.unescape(m.group(2))
            name = fetch(url) if CLICKUP_FILE.fullmatch(url) else None
            return f'{m.group(1)} {mark}="{html.escape(name)}"' if name else m.group(0)
        return inner

    body = re.sub(r'(<img\b[^>]*?)\ssrc="([^"]+)"', swap("data-mawesi-img"), body)
    return re.sub(r'(<a\b[^>]*?)\shref="([^"]+)"', swap("data-mawesi-file"), body)


def hierarchy(cu: ClickUp, projects) -> dict:
    """(tipo, id) -> identificador del proyecto MWSTASKS, para espacios, carpetas y listas configurados."""
    where = {}
    for p in projects:
        sid, ident = p["space"], p["identifier"]
        where[(SPACE, sid)] = ident
        for arch in ("false", "true"):
            for f in cu.get(f"/space/{sid}/folder", archived=arch).get("folders", []):
                where[(FOLDER, f["id"])] = ident
                for lst in f.get("lists", []):
                    where[(LIST, lst["id"])] = ident
                for lst in cu.get(f"/folder/{f['id']}/list", archived="true").get("lists", []):
                    where[(LIST, lst["id"])] = ident
            for lst in cu.get(f"/space/{sid}/list", archived=arch).get("lists", []):
                where[(LIST, lst["id"])] = ident
    return where


def v3(cu: ClickUp, path: str, **params):
    """GET a la API v3 de ClickUp (Docs) con el mismo cliente: reintentos y ritmo."""
    return cu.get(path, base=V3, **params)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, help="sync.json (proyectos y espacios)")
    ap.add_argument("--out", required=True, help="carpeta del paquete (se crea con permisos 700)")
    ap.add_argument("--team", default="30902916")
    ap.add_argument("--default-project", default="MWI")
    ap.add_argument("--max-file-mb", type=int, default=100, help="igual que el límite de adjuntos de MWSTASKS")
    a = ap.parse_args()

    cu = ClickUp(os.environ["CLICKUP_TOKEN"])
    os.makedirs(os.path.join(a.out, "images"), mode=0o700, exist_ok=True)
    os.chmod(a.out, 0o700)
    projects = json.load(open(a.config))["projects"]
    where = hierarchy(cu, projects)
    emails = {m["user"]["id"]: (m["user"].get("email") or "").lower() for m in cu.get("/team").get("teams", [{}])[0].get("members", [])}

    docs, cursor = [], None
    while True:
        data = v3(cu, f"/workspaces/{a.team}/docs", limit=100, cursor=cursor)
        docs += data.get("docs", [])
        cursor = data.get("next_cursor")
        if not cursor:
            break

    out, report = [], {"docs": len(docs), "copiados": 0, "omitidos": {}, "sin acceso": [], "avisos": []}
    warn = report["avisos"].append
    for d in docs:
        if d.get("deleted") or d.get("archived"):
            continue
        try:
            pages = v3(cu, f"/workspaces/{a.team}/docs/{d['id']}/pages", content_format="text/md", max_page_depth=-1)
        except RuntimeError as e:
            if " 403 " in str(e) or " 401 " in str(e):
                report["sin acceso"].append(d["name"])
                continue
            raise
        pages = pages if isinstance(pages, list) else pages.get("pages", [])
        reason = is_skipped(d["name"], pages)
        if reason:
            report["omitidos"][reason] = report["omitidos"].get(reason, 0) + 1
            continue
        parent = d.get("parent") or {}
        ptype, pid = parent.get("type"), str(parent.get("id"))
        body = localize(doc_html(pages), a.out, cu, a.max_file_mb * 1024 * 1024, warn)
        updated = max([int(d.get("date_updated") or 0)] + [int(p.get("date_updated") or 0) for p, _ in walk(pages)])
        stamp = datetime.fromtimestamp(updated / 1000, tz=timezone.utc).strftime("%Y-%m-%d") if updated else ""
        body += f"<p><em>Migrado de ClickUp: {html.escape(d['name'])}{' · actualizado ' + stamp if stamp else ''}</em></p>"
        out.append({
            "external_id": d["id"],
            "name": d["name"].strip()[:255],
            "html": body,
            "project": None if ptype == TASK else where.get((ptype, pid), a.default_project),
            "task": pid if ptype == TASK else None,
            "default_project": a.default_project,
            "owner_email": emails.get(d.get("creator")),
            "private": d["name"].strip().lower() == "personal docs",
            "created_at": int(d.get("date_created") or 0),
        })
        report["copiados"] += 1

    with open(os.path.join(a.out, "pages.json"), "w") as f:
        json.dump(out, f)
    report["archivos e imágenes"] = len(os.listdir(os.path.join(a.out, "images")))
    report["llamadas ClickUp"] = cu.calls
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
