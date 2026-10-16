# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Respaldo completo de ClickUp en disco, para tenerlo después de cancelar. SOLO LECTURA (GET).

  CLICKUP_TOKEN=... python -m tools.migrate_clickup.backup --out <carpeta>

Qué guarda (todos los espacios, incluidos los archivados):
- `workspace.json`: equipo, personas y espacios.
- `spaces/<id>/structure.json`: carpetas, listas (con sus estados) y campos propios de cada lista.
- `spaces/<id>/lists/<id>.json`: tareas de la lista (abiertas, cerradas y archivadas, con subtareas).
- `tasks/<xx>/<id>.json`: detalle de cada tarea (descripción, checklists, campos, adjuntos) + comentarios
  con sus respuestas (todas las páginas, no solo las 25 últimas).
- `files/<id-tarea>/`: adjuntos de la tarea y todo archivo alojado en ClickUp que aparezca en la tarea o sus
  comentarios. Sin límite de tamaño.
- `time_entries.json`: horas registradas de todas las personas, desde 2018.
- `docs/<id>.json` + `docs/files/`: Docs con todas sus páginas en markdown y sus imágenes/archivos.
- `index.csv`: una fila por tarea (para buscar con Excel) y `summary.json` (conteos y errores).

Se puede cortar y volver a correr: lo que ya está en disco no se vuelve a pedir.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .clickup import ClickUp

V3 = "https://api.clickup.com/api/v3"
FILE_URL = re.compile(r"https://t\d+\.p\.clickup-attachments\.com/[^\s\"'\\)\]>]+")
COMMENT_PAGE = 25  # ClickUp devuelve los comentarios de a 25, del más nuevo al más viejo
CHUNK = 1 << 20


def safe_name(name: str, limit: int = 120) -> str:
    """Nombre de archivo sin barras ni caracteres raros, conservando la extensión."""
    name = re.sub(r"[^\w.\- ()áéíóúñÁÉÍÓÚÑ]", "_", urllib.parse.unquote(name or "")).strip(" .") or "archivo"
    if len(name) <= limit:
        return name
    stem, dot, ext = name.rpartition(".")
    return f"{stem[:limit - len(ext) - 1]}.{ext}" if dot and len(ext) <= 10 else name[:limit]


def url_name(url: str) -> str:
    """Nombre estable y único por URL: el mismo archivo no se baja dos veces."""
    path = urllib.parse.urlsplit(url).path
    return f"{hashlib.sha1(url.encode()).hexdigest()[:10]}-{safe_name(path.rsplit('/', 1)[-1], 90)}"


def file_urls(record) -> list[str]:
    """URLs de archivos alojados en ClickUp que aparecen en cualquier parte de un JSON (descripción, comentarios)."""
    seen = []
    for u in FILE_URL.findall(json.dumps(record, ensure_ascii=False)):
        u = u.rstrip(".,;")
        if u not in seen:
            seen.append(u)
    return seen


def all_comments(cu: ClickUp, path: str) -> list:
    """Todas las páginas de comentarios (ClickUp pagina con start=<fecha> y start_id=<id> del más viejo)."""
    out, params = [], {}
    while True:
        page = cu.get(path, **params).get("comments", [])
        new = [c for c in page if c["id"] not in {o["id"] for o in out}]
        out += new
        if len(page) < COMMENT_PAGE or not new:
            return out
        oldest = page[-1]
        params = {"start": oldest["date"], "start_id": oldest["id"]}


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    tmp = f"{path}.part"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def read_json(path: str):
    with open(path) as f:
        return json.load(f)


class Backup:
    def __init__(self, cu: ClickUp, out: str, team: str, since: str):
        self.cu, self.out, self.team, self.since = cu, out, team, since
        self.errors: list[str] = []
        self.stats = {"espacios": 0, "listas": 0, "tareas": 0, "comentarios": 0, "archivos": 0, "MB": 0.0,
                      "horas registradas": 0, "docs": 0, "docs sin acceso": 0}

    def p(self, *parts) -> str:
        return os.path.join(self.out, *parts)

    def log(self, msg: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    def cached(self, path: str, fetch):
        if os.path.exists(path):
            return read_json(path)
        data = fetch()
        write_json(path, data)
        return data

    # ---------- archivos ----------
    def download(self, url: str, path: str) -> None:
        """Baja en partes (sirve para videos de varios GB) a .part y renombra al terminar."""
        if os.path.exists(path):
            return
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        tmp = f"{path}.part"
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url), timeout=300) as r, open(tmp, "wb") as f:
                    while chunk := r.read(CHUNK):
                        f.write(chunk)
                os.replace(tmp, path)
                self.stats["archivos"] += 1
                self.stats["MB"] = round(self.stats["MB"] + os.path.getsize(path) / 1048576, 1)
                return
            except urllib.error.HTTPError as e:
                if e.code < 500 or attempt == 3:
                    self.errors.append(f"archivo {e.code}: {url[:120]}")
                    return
            except (urllib.error.URLError, OSError) as e:
                if attempt == 3:
                    self.errors.append(f"archivo ({e}): {url[:120]}")
                    return
            time.sleep(5 * (attempt + 1))

    # ---------- estructura ----------
    def workspace(self) -> list:
        def fetch():
            teams = self.cu.get("/team").get("teams", [])
            spaces = []
            for arch in ("false", "true"):
                spaces += self.cu.get(f"/team/{self.team}/space", archived=arch).get("spaces", [])
            return {"teams": teams, "spaces": spaces}
        return self.cached(self.p("workspace.json"), fetch)["spaces"]

    def structure(self, sid: str) -> dict:
        def fetch():
            folders = []
            for arch in ("false", "true"):
                for f in self.cu.get(f"/space/{sid}/folder", archived=arch).get("folders", []):
                    f["archived_lists"] = self.cu.get(f"/folder/{f['id']}/list", archived="true").get("lists", [])
                    folders.append(f)
            loose = []
            for arch in ("false", "true"):
                loose += self.cu.get(f"/space/{sid}/list", archived=arch).get("lists", [])
            lists = {}
            for lst in loose + [l for f in folders for l in f.get("lists", []) + f["archived_lists"]]:
                lists[lst["id"]] = {"list": self.cu.get(f"/list/{lst['id']}"),
                                    "fields": self.cu.get(f"/list/{lst['id']}/field").get("fields", [])}
            return {"folders": folders, "folderless_lists": loose, "lists": lists}
        return self.cached(self.p("spaces", sid, "structure.json"), fetch)

    def list_tasks(self, sid: str, lid: str) -> list:
        def fetch():
            tasks = []
            for arch in ("false", "true"):
                page = 0
                while True:
                    data = self.cu.get(f"/list/{lid}/task", page=page, include_closed="true", subtasks="true",
                                       include_markdown_description="true", archived=arch)
                    tasks += data.get("tasks", [])
                    if data.get("last_page", True) or not data.get("tasks"):
                        break
                    page += 1
            return tasks
        return self.cached(self.p("spaces", sid, "lists", f"{lid}.json"), fetch)

    # ---------- tareas ----------
    def task(self, tid: str) -> dict:
        def fetch():
            detail = self.cu.get(f"/task/{tid}", include_markdown_description="true")
            comments = all_comments(self.cu, f"/task/{tid}/comment")
            for c in comments:
                c["replies"] = self.cu.get(f"/comment/{c['id']}/reply").get("comments", []) if int(c.get("reply_count") or 0) else []
            return {"task": detail, "comments": comments}
        try:
            rec = self.cached(self.p("tasks", tid[:2], f"{tid}.json"), fetch)
        except RuntimeError as e:  # tarea borrada o sin acceso: se anota y sigue
            self.errors.append(f"tarea {tid}: {e}")
            return {}
        self.files(tid, rec)
        return rec

    def files(self, tid: str, rec: dict) -> list[str]:
        folder = self.p("files", tid)
        names, by_url = [], {}
        for a in rec["task"].get("attachments") or []:
            if a.get("url"):
                by_url[a["url"]] = f"{a['id']}-{safe_name(a.get('title') or a['url'].rsplit('/', 1)[-1])}"
        for u in file_urls(rec):
            by_url.setdefault(u, url_name(u))
        for url, name in by_url.items():
            self.download(url, os.path.join(folder, name))
            names.append(name)
        return names

    # ---------- horas y docs ----------
    def time_entries(self, people: set) -> None:
        path = self.p("time_entries.json")
        if os.path.exists(path):
            self.stats["horas registradas"] = len(read_json(path))
            return
        start = int(datetime.strptime(self.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
        end = int(time.time() * 1000)
        entries, ids = {}, sorted(people)
        for k in range(0, len(ids), 10):
            for e in self.cu.get(f"/team/{self.team}/time_entries", start_date=start, end_date=end,
                                 assignee=",".join(map(str, ids[k:k + 10])), include_location_names="true").get("data", []):
                entries[e["id"]] = e
        write_json(path, list(entries.values()))
        self.stats["horas registradas"] = len(entries)

    def docs(self) -> None:
        docs = {}
        for arch in ("false", "true"):
            cursor = None
            while True:
                data = self.cu.get(f"/workspaces/{self.team}/docs", base=V3, limit=100, cursor=cursor, deleted="false", archived=arch)
                docs.update({d["id"]: d for d in data.get("docs", [])})
                cursor = data.get("next_cursor")
                if not cursor:
                    break
        for d in docs.values():
            path = self.p("docs", f"{d['id']}.json")
            if not os.path.exists(path):
                try:
                    pages = self.cu.get(f"/workspaces/{self.team}/docs/{d['id']}/pages", base=V3,
                                        content_format="text/md", max_page_depth=-1)
                except RuntimeError as e:
                    if " 403 " in str(e) or " 401 " in str(e):
                        self.stats["docs sin acceso"] += 1
                        self.errors.append(f"doc sin acceso: {d.get('name')} ({d['id']})")
                        continue
                    raise
                write_json(path, {"doc": d, "pages": pages if isinstance(pages, list) else pages.get("pages", [])})
            for u in file_urls(read_json(path)):
                self.download(u, self.p("docs", "files", url_name(u)))
            self.stats["docs"] += 1

    # ---------- todo ----------
    def run(self) -> None:
        os.makedirs(self.out, mode=0o700, exist_ok=True)
        spaces = list({str(s["id"]): s for s in self.workspace()}.values())
        people = {m["user"]["id"] for t in read_json(self.p("workspace.json"))["teams"] for m in t.get("members", [])}
        rows, done = [], set()
        for s in spaces:
            sid = str(s["id"])
            st = self.structure(sid)
            self.stats["espacios"] += 1
            folder_of = {l["id"]: f["name"] for f in st["folders"] for l in f.get("lists", []) + f["archived_lists"]}
            for lid, info in st["lists"].items():
                tasks = self.list_tasks(sid, lid)
                self.stats["listas"] += 1
                self.log(f"{s['name']} / {folder_of.get(lid, '(sin carpeta)')} / {info['list'].get('name')}: {len(tasks)} tareas")
                for t in tasks:
                    if t["id"] in done:  # una tarea puede estar en varias listas
                        continue
                    done.add(t["id"])
                    rec = self.task(t["id"])
                    if not rec:
                        continue
                    self.stats["comentarios"] += sum(1 + len(c["replies"]) for c in rec["comments"])
                    for who in [t.get("creator") or {}] + (t.get("assignees") or []):
                        if who.get("id"):
                            people.add(who["id"])
                    for c in rec["comments"]:
                        for item in [c] + c["replies"]:
                            if (item.get("user") or {}).get("id"):
                                people.add(item["user"]["id"])
                    rows.append(self.index_row(s, folder_of.get(lid, ""), info["list"], t, rec))
        self.log(f"Horas de {len(people)} personas…")
        self.time_entries(people)
        self.log("Docs…")
        self.docs()
        self.write_index(rows)
        self.stats["llamadas ClickUp"] = self.cu.calls
        write_json(self.p("summary.json"), {"fecha": datetime.now(timezone.utc).isoformat(), **self.stats, "errores": self.errors})
        self.log(json.dumps({**self.stats, "errores": len(self.errors)}, ensure_ascii=False))

    def index_row(self, space, folder, lst, t, rec) -> list:
        ms = lambda v: datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc).strftime("%Y-%m-%d") if v else ""
        files = os.path.join("files", t["id"])
        has_files = os.path.isdir(self.p(files))
        return [t["id"], t.get("custom_id") or "", space["name"], folder, lst.get("name", ""), t.get("name", ""),
                (t.get("status") or {}).get("status", ""), ", ".join(a.get("username") or a.get("email") or "" for a in t.get("assignees") or []),
                ms(t.get("date_created")), ms(t.get("date_closed")), t.get("parent") or "", len(rec["comments"]),
                len(os.listdir(self.p(files))) if has_files else 0, f"tasks/{t['id'][:2]}/{t['id']}.json",
                files if has_files else "", t.get("url", "")]

    def write_index(self, rows: list) -> None:
        with open(self.p("index.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "id_propio", "espacio", "carpeta", "lista", "tarea", "estado", "responsables", "creada",
                        "cerrada", "padre", "comentarios", "archivos", "json", "carpeta_archivos", "url_clickup"])
            w.writerows(rows)
        self.stats["tareas"] = len(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="carpeta del respaldo (se crea con permisos 700)")
    ap.add_argument("--team", default="30902916")
    ap.add_argument("--since", default="2018-01-01", help="horas registradas desde esta fecha")
    ap.add_argument("--min-interval", type=float, default=0.75, help="segundos entre pedidos (deja lugar a la copia incremental)")
    a = ap.parse_args()
    Backup(ClickUp(os.environ["CLICKUP_TOKEN"], min_interval=a.min_interval), a.out, a.team, a.since).run()


if __name__ == "__main__":
    main()
