# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Copia incremental ClickUp -> MWSTASKS, para el período entre la migración y el corte.

- ClickUp: SOLO LECTURA. Una sola dirección: lo editado en MWSTASKS se pisa con lo de ClickUp.
- Cada corrida pide a ClickUp solo las tareas cambiadas desde la corrida anterior (un pedido para todos los espacios)
  y, por proyecto con cambios: crea las nuevas, actualiza las existentes (solo los campos que cambiaron), las mueve de
  módulo o ciclo si cambiaron de lista, y agrega comentarios, adjuntos y horas nuevos.
- Horas: revisa una ventana de días hacia atrás (ClickUp no marca la tarea como cambiada al cargar horas).
- --prune: compara todas las tareas y marca con la etiqueta "Borrada en ClickUp" las que ya no existen allá
  (borradas, archivadas o movidas fuera del alcance). No borra nada en MWSTASKS.
- El estado (última corrida, lista y descripción de cada tarea, horas ya copiadas) vive en --state.

Uso:
  CLICKUP_TOKEN=... MWSTASKS_TOKEN=... python -m tools.migrate_clickup.sync --config sync.json --state state.json \
    --url https://tasks.mawesi.online
"""
import argparse
import collections
import json
import os
import sys
import time

from tools.migrate_clickup import mapping as M
from tools.migrate_clickup.clickup import ClickUp
from tools.migrate_clickup.migrate import Migration, send_relations
from tools.migrate_clickup.plane import Plane, PlaneError

OVERLAP_MS = 5 * 60 * 1000  # se vuelve a pedir un margen: relojes distintos y tareas editadas durante la corrida
DELETED_LABEL = "Borrada en ClickUp"


class ProjectSync(Migration):
    """Una corrida de Migration acotada a las tareas cambiadas de un proyecto."""

    def __init__(self, cu, pl, args, project, changed, state):
        super().__init__(cu, pl, argparse.Namespace(
            space=project["space"], folders=",".join(project.get("folders", [])), team=args.team,
            project_name=project["identifier"], identifier=project["identifier"], estimate=True,
            skip_comments=False, skip_attachments=False, skip_time=False, max_file_mb=args.max_file_mb, comments_start=1,
            time_from=time.strftime("%Y-%m-%d", time.localtime(time.time() - args.time_days * 86400))))
        self.changed, self.state = changed, state
        self.found = {}  # id ClickUp -> issue de MWSTASKS (o None), para no buscar dos veces

    def read_clickup(self):
        # La estructura (listas, estados, campos) se lee entera: es poca y hace falta para mapear.
        # Las tareas no: son solo las cambiadas, que ya vinieron en un único pedido.
        self.read_tasks = False
        super().read_clickup()
        self.tasks = {t["id"]: t for t in self.changed}

    def project(self):
        found = [p for p in self.pl.all(self.pl.ws("projects/")) if p["identifier"] == self.a.identifier]
        if not found:  # la copia incremental nunca crea proyectos
            raise RuntimeError(f"El proyecto {self.a.identifier} no existe en MWSTASKS")
        self.pid = found[0]["id"]

    def find_issue(self, task_id):
        if task_id not in self.found:
            try:
                self.found[task_id] = self.pl.get(self.pl.proj(self.pid, "issues/"), external_id=task_id,
                                                  external_source=M.SOURCE)
            except PlaneError as e:
                if e.code != 404:
                    raise
                self.found[task_id] = None
        return self.found[task_id]

    def issues(self):
        self.issue_by_task, self.new_issues, self.parent_of = {}, set(), {}
        tasks_state = self.state.setdefault("tasks", {})
        ordered = sorted(self.tasks.values(), key=lambda t: int(t.get("date_created") or 0))
        desc = {}
        for t in ordered:
            current = self.find_issue(t["id"])
            if current is None:
                self.create_issue(t)
                desc[t["id"]] = M.text_hash(M.description_html(t))
            else:
                iid = self.issue_by_task[t["id"]] = current["id"]
                self.parent_of[iid] = current.get("parent")
                wanted = self.issue_body(t)
                desc[t["id"]] = M.text_hash(wanted["description_html"])
                diff = M.issue_changes(current, wanted, tasks_state.get(t["id"], {}).get("desc") != desc[t["id"]])
                if diff:
                    self.pl.write("PATCH", self.pl.proj(self.pid, f"issues/{iid}/"), diff)
                    self.stats["tareas actualizadas"] += 1
        for t in ordered:  # padres fuera de los cambios: se buscan en MWSTASKS
            if t.get("parent") and t["parent"] not in self.issue_by_task:
                parent = self.find_issue(t["parent"])
                if parent:
                    self.issue_by_task[t["parent"]] = parent["id"]
            iid = self.issue_by_task.get(t["id"])
            if iid and not t.get("parent") and self.parent_of.get(iid):  # dejó de ser subtarea en ClickUp
                self.pl.write("PATCH", self.pl.proj(self.pid, f"issues/{iid}/"), {"parent": None})
                self.stats["subtareas desenlazadas"] += 1
        self.link_parents([t for t in ordered if t.get("parent")])
        for t in ordered:
            if t["id"] in self.issue_by_task:
                tasks_state[t["id"]] = {"list": t["list"]["id"], "desc": desc[t["id"]]}

    def grouping(self):
        # Si la tarea cambió de lista, sale del módulo o ciclo viejo; después se agrega al nuevo.
        for t in self.tasks.values():
            iid, old_list = self.issue_by_task.get(t["id"]), self.moved_from.get(t["id"])
            if not iid or not old_list or old_list == t["list"]["id"]:
                continue
            for kind, by_list in (("module", self.module_by_list), ("cycle", self.cycle_by_list)):
                old = by_list.get(old_list)
                if old and old != by_list.get(t["list"]["id"]):
                    try:
                        self.pl.write("DELETE", self.pl.proj(self.pid, f"{kind}s/{old}/{kind}-issues/{iid}/"))
                        self.stats[f"tareas sacadas de {kind}"] += 1
                    except PlaneError as e:
                        if e.code != 404:
                            self.warn(f"no se pudo sacar de {kind}", f"{t['id']}: {e}")
        super().grouping()

    def comments(self):
        # Antes de copiar, mira qué comentarios ya están: evita un POST (y un 409) por cada comentario viejo.
        self.done_comments = {}
        for tid, iid in self.issue_by_task.items():
            if tid in self.tasks:
                self.done_comments[iid] = {c.get("external_id") for c in self.pl.all(self.pl.proj(self.pid, f"issues/{iid}/comments/"))}
        keep, self.issue_by_task = self.issue_by_task, {k: v for k, v in self.issue_by_task.items() if k in self.tasks}
        try:
            super().comments()
        finally:
            self.issue_by_task = keep

    def post_comment(self, iid, body):
        if body["external_id"] in self.done_comments.get(iid, ()):
            return False
        return super().post_comment(iid, body)

    def worklogs(self):
        # Ruta cada hora a su tarea aunque la tarea no haya cambiado; las ya copiadas se saltan sin pedir nada.
        seen = self.state.setdefault("entries", {})
        self.skip_entry = lambda e: str(e["id"]) in seen
        self.route_task = lambda tid: (self.find_issue(tid) or {}).get("id")
        super().worklogs()
        for eid in self.copied_entries:
            seen[str(eid)] = int(time.time())

    def run_sync(self):
        self.moved_from = {t["id"]: self.state.get("tasks", {}).get(t["id"], {}).get("list") for t in self.changed}
        self.setup()
        if self.changed:
            self.read_clickup()
            self.people(); self.project()
            self.states(); self.labels(); self.cycles_and_modules(); self.properties()
            self.issues(); self.grouping(); self.relations(); self.values(); self.comments()
        else:  # sin tareas cambiadas: solo horas nuevas
            self.tasks, self.issue_by_task = {}, {}
            self.people(); self.project()
        self.worklogs()
        return self.report()


def prune(cu, pl, cfg, args):
    """Marca en MWSTASKS las tareas que ya no están en ClickUp. Lee todo: correr de noche."""
    report = collections.Counter()
    alive = collections.defaultdict(set)
    pairs, deps = set(), set()
    spaces = sorted({str(p["space"]) for p in cfg["projects"]})
    for t in cu.team_tasks(args.team, spaces):
        for p in cfg["projects"]:
            if M.in_scope(t, p["space"], set(p.get("folders", []))):
                alive[p["identifier"]].add(t["id"])
                pairs |= M.relation_pairs([t])
                deps |= M.dependency_pairs([t])
    projects = {p["identifier"]: p["id"] for p in pl.all(pl.ws("projects/"))}
    for ident in sorted({p["identifier"] for p in cfg["projects"]}):
        pid = projects.get(ident)
        if not pid or not alive[ident]:  # sin tareas vivas leídas = algo salió mal: no se marca nada
            report[f"{ident}: saltado"] += 1
            continue
        labels = {lb["name"]: lb["id"] for lb in pl.all(pl.proj(pid, "labels/"))}
        label = labels.get(DELETED_LABEL) or pl.write("POST", pl.proj(pid, "labels/"), {"name": DELETED_LABEL, "color": "#94a3b8"})["id"]
        for i in pl.all(pl.proj(pid, "issues/")):
            if i.get("external_source") != M.SOURCE or i.get("external_id") in alive[ident] or label in (i.get("labels") or []):
                continue
            pl.write("PATCH", pl.proj(pid, f"issues/{i['id']}/"), {"labels": list(i.get("labels") or []) + [label]})
            report[f"{ident}: marcadas como borradas"] += 1
    # Relaciones y dependencias: ClickUp no siempre marca la tarea como cambiada al unirla con otra; de noche se revisan todas.
    # Van al final: si fallan, las marcas de "Borrada en ClickUp" ya quedaron.
    for key, n in send_relations(pl, pairs).items():
        report[f"relaciones {key.replace('_', ' ')}"] += n
    for key, n in send_relations(pl, deps, "blocked_by").items():
        report[f"dependencias {key.replace('_', ' ')}"] += n
    return dict(report)


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, data):
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)  # si la corrida se corta, el estado anterior queda entero


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, help='{"workspace": "...", "projects": [{"identifier", "space", "folders"}]}')
    ap.add_argument("--state", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--team", default="")
    ap.add_argument("--since", default="", help="AAAA-MM-DD HH:MM (solo la primera vez, si no hay estado)")
    ap.add_argument("--time-days", type=int, default=45, help="ventana de horas a revisar")
    ap.add_argument("--max-file-mb", type=int, default=100)
    ap.add_argument("--plane-interval", type=float, default=1.05, help="segundos entre pedidos (límite 60/minute)")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--tasks", default="", help="ids de ClickUp separados por coma: vuelve a copiar solo esas tareas "
                                                "(p. ej. comentarios que faltaron); no mueve el punto de la copia incremental")
    a = ap.parse_args()
    cfg, state = load(a.config, None), load(a.state, {})
    cu = ClickUp(os.environ["CLICKUP_TOKEN"])
    pl = Plane(a.url, os.environ["MWSTASKS_TOKEN"], cfg["workspace"], min_interval=a.plane_interval)
    a.team = a.team or str(cu.get("/team")["teams"][0]["id"])
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    if a.prune:
        print(json.dumps({"hora": stamp, "prune": prune(cu, pl, cfg, a)}, ensure_ascii=False))
        return 0
    if "since" not in state:
        if not a.since:
            sys.exit("Primera corrida: falta --since (desde cuándo buscar cambios en ClickUp)")
        state["since"] = int(time.mktime(time.strptime(a.since, "%Y-%m-%d %H:%M")) * 1000)
    started = int(time.time() * 1000)
    spaces = sorted({str(p["space"]) for p in cfg["projects"]})
    if a.tasks:
        changed = [cu.get(f"/task/{tid.strip()}", include_markdown_description="true") for tid in a.tasks.split(",") if tid.strip()]
    else:
        changed = list(cu.team_tasks(a.team, spaces, updated_gt=state["since"] - OVERLAP_MS))
    out, failed = {"hora": stamp, "cambiadas en ClickUp": len(changed)}, False
    for p in cfg["projects"]:
        mine = [t for t in changed if M.in_scope(t, p["space"], set(p.get("folders", [])))]
        key = f"{p['identifier']} ({p['space']})"
        try:
            job = ProjectSync(cu, pl, a, p, mine, state)
            job.log = lambda msg: None  # el cron guarda solo el resumen
            rep = job.run_sync()
            out[key] = {**rep["creado"], **({"avisos": rep["avisos"]} if rep["avisos"] else {})}
        except Exception as e:  # noqa: BLE001 - un proyecto con error no frena a los demás
            failed = True
            out[key] = {"error": str(e)[:300]}
    if not failed and not a.tasks:  # si algo falló, la próxima corrida vuelve a pedir desde el mismo punto
        state["since"] = started
    save(a.state, state)
    print(json.dumps(out, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
