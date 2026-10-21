# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Migra un espacio de ClickUp a un proyecto de MWSTASKS.

- ClickUp: SOLO LECTURA (solo pedidos GET).
- Idempotente: todo lo creado lleva external_source="clickup" + external_id. Si se corre de nuevo, salta lo que ya existe.
- Las personas se cruzan por email. Si alguien no tiene cuenta, la tarea queda sin esa persona y se avisa.

Uso:
  CLICKUP_TOKEN=... MWSTASKS_TOKEN=... uv run --with-requirements tools/migrate_clickup/requirements.txt \
    python -m tools.migrate_clickup.migrate --space 90144438515 --folders "Product,Sprints,Documentation" \
    --url http://localhost:8088 --workspace mawesi --project-name "Contractor Management" --identifier CM
"""
import argparse
import collections
import json
import os
import sys
import time

from tools.migrate_clickup import mapping as M
from tools.migrate_clickup.clickup import ClickUp
from tools.migrate_clickup.plane import Plane, PlaneError

ADMIN, MEMBER = 20, 15
RELATIONS_PER_CALL = 1000  # igual que plane_mawesi.views.relations.MAX_PAIRS


def send_relations(pl: Plane, pairs) -> collections.Counter:
    """Pares de ids ClickUp -> relaciones "relacionada con". El endpoint solo crea las que faltan (idempotente)."""
    out, pairs = collections.Counter(), sorted(pairs)
    for k in range(0, len(pairs), RELATIONS_PER_CALL):
        r = pl.write("POST", pl.mawesi_ws("relations/"),
                     {"external_source": M.SOURCE, "pairs": [list(p) for p in pairs[k:k + RELATIONS_PER_CALL]]})
        for key in ("creadas", "ya_estaban", "sin_tarea"):
            out[key] += int((r or {}).get(key) or 0)
    return out


class Migration:
    def __init__(self, cu: ClickUp, pl: Plane, args):
        self.cu, self.pl, self.a = cu, pl, args
        self.stats = collections.Counter()
        self.warnings = collections.Counter()
        self.samples = collections.defaultdict(list)
        self.read_tasks = True  # la copia incremental trae las tareas por otro lado

    def warn(self, kind, detail=""):
        self.warnings[kind] += 1
        if len(self.samples[kind]) < 3 and detail:
            self.samples[kind].append(detail)

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    # ---------- 1. leer ClickUp ----------
    def read_clickup(self):
        wanted = {f.strip() for f in self.a.folders.split(",") if f.strip()}
        self.lists, self.tasks, self.fields = [], {}, {}
        groups = [(f["name"], f["lists"]) for f in self.cu.folders(self.a.space)]
        groups.append((M.LOOSE, self.cu.folderless_lists(self.a.space)))  # listas fuera de carpetas
        for folder, lists in groups:
            if wanted and folder not in wanted:
                continue
            for lst in lists:
                lst = {**lst, "folder": folder}
                detail = self.cu.list(lst["id"])
                lst["statuses"] = detail.get("statuses", [])
                self.lists.append(lst)
                for fd in self.cu.custom_fields(lst["id"]):
                    self.fields.setdefault(fd["id"], fd)
                if self.read_tasks:
                    for t in self.cu.tasks(lst["id"]):
                        self.tasks[t["id"]] = t
        self.log(f"ClickUp: {len(self.lists)} listas, {len(self.tasks)} tareas, {len(self.fields)} campos")

    # ---------- 2. preparar MWSTASKS ----------
    def people(self):
        members = self.pl.all(self.pl.ws("members/"))
        self.user_by_email = {(m.get("email") or "").lower(): m["id"] for m in members if m.get("email")}
        self.cu_user = {}  # id ClickUp -> id MWSTASKS
        for t in self.tasks.values():
            for u in t.get("assignees", []) + [t.get("creator") or {}]:
                if u.get("id") and u["id"] not in self.cu_user:
                    self.cu_user[u["id"]] = self.user_by_email.get((u.get("email") or "").lower())
        missing = [k for k, v in self.cu_user.items() if v is None]
        if missing:
            self.warn("personas sin cuenta en MWSTASKS", ", ".join(map(str, missing)))

    def project(self):
        found = [p for p in self.pl.all(self.pl.ws("projects/")) if p["identifier"] == self.a.identifier]
        if found:
            self.pid = found[0]["id"]
            self.log(f"Proyecto existente {self.a.identifier} ({self.pid})")
        else:
            p = self.pl.write("POST", self.pl.ws("projects/"), {
                "name": self.a.project_name, "identifier": self.a.identifier,
                "description": f"Migrado de ClickUp (espacio {self.a.space}).",
                "external_source": M.SOURCE, "external_id": str(self.a.space), "timezone": "America/Bogota",
                "cycle_view": True, "module_view": True,
            })
            self.pid = p["id"]
            self.stats["proyecto creado"] += 1
            self.log(f"Proyecto creado {self.a.identifier} ({self.pid})")
        current = {m["id"] for m in self.pl.all(self.pl.proj(self.pid, "members/"))}
        for uid in set(self.user_by_email.values()) - current:
            try:
                self.pl.write("POST", self.pl.proj(self.pid, "project-members/"), {"member": uid, "role": MEMBER})
                self.stats["miembros agregados"] += 1
            except PlaneError as e:
                self.warn("miembro no agregado", str(e))

    def _by_external(self, path):
        return {x["external_id"]: x["id"] for x in self.pl.all(path) if x.get("external_source") == M.SOURCE and x.get("external_id")}

    def states(self):
        """Los 7 estados del flujo estándar (M.STANDARD_STATES); cada estado de ClickUp se traduce a uno de ellos."""
        existing = {s["name"].lower(): s["id"] for s in self.pl.all(self.pl.proj(self.pid, "states/"))}
        self.state_ids = {}
        for name, group, color, sequence in M.STANDARD_STATES:
            if name.lower() not in existing:
                body = {"name": name, "color": color, "group": group, "sequence": sequence,
                        "external_source": M.SOURCE, "external_id": f"std:{name.lower()}"}
                existing[name.lower()] = self.pl.write("POST", self.pl.proj(self.pid, "states/"), body)["id"]
                self.stats["estados"] += 1
            self.state_ids[name] = existing[name.lower()]

    def state_of(self, t):
        return self.state_ids[M.standard_state(t["status"].get("type") or "custom", t["status"]["status"])]

    def labels(self):
        existing = self._by_external(self.pl.proj(self.pid, "labels/"))
        tags = {}
        for t in self.tasks.values():
            for tag in t.get("tags", []):
                tags.setdefault(tag["name"].lower(), tag)
            if tag := M.status_tag(t["status"]["status"]):
                tags.setdefault(tag["name"], tag)
        self.label_by_name = {}
        for key, tag in tags.items():
            ext = f"tag:{key}"
            if ext not in existing:
                existing[ext] = self.pl.write("POST", self.pl.proj(self.pid, "labels/"), {
                    "name": tag["name"][:255], "color": tag.get("tag_bg") or "#64748b",
                    "external_source": M.SOURCE, "external_id": ext})["id"]
                self.stats["etiquetas"] += 1
            self.label_by_name[key] = existing[ext]

    def labels_of(self, t):
        names = [tag["name"].lower() for tag in t.get("tags", [])]
        if tag := M.status_tag(t["status"]["status"]):
            names.append(tag["name"])  # lo que el flujo estándar no tiene como estado (bug, staging)
        return list(dict.fromkeys(self.label_by_name[n] for n in names))

    def cycles_and_modules(self):
        cycles = {c["external_id"]: c for c in self.pl.all(self.pl.proj(self.pid, "cycles/"))
                  if c.get("external_source") == M.SOURCE and c.get("external_id")}
        modules = {m["external_id"]: m for m in self.pl.all(self.pl.proj(self.pid, "modules/"))
                   if m.get("external_source") == M.SOURCE and m.get("external_id")}
        self.cycle_by_list, self.module_by_list, self.cycle_info = {}, {}, {}
        for lst in self.lists:
            ext = f"list:{lst['id']}"
            if M.is_sprint(lst["name"]):
                # Plane no deja agregar tareas (ni editar) un ciclo con fecha de fin pasada:
                # se crea SIN fechas y las fechas se ponen en grouping(), después de cargar las tareas.
                if ext not in cycles:
                    cycles[ext] = self.pl.write("POST", self.pl.proj(self.pid, "cycles/"), {
                        "name": lst["name"][:255], "external_source": M.SOURCE, "external_id": ext,
                        "owned_by": self.me})
                    self.stats["ciclos"] += 1
                c = cycles[ext]
                self.cycle_by_list[lst["id"]] = c["id"]
                self.cycle_info[c["id"]] = {"has_dates": bool(c.get("end_date")),
                                            "start": M.ms_to_date(lst.get("start_date")),
                                            "end": M.ms_to_date(lst.get("due_date"))}
            else:
                name = M.module_name(lst["folder"], lst["name"])
                if ext not in modules:
                    modules[ext] = self.pl.write("POST", self.pl.proj(self.pid, "modules/"), {
                        "name": name, "external_source": M.SOURCE, "external_id": ext})
                    self.stats["módulos"] += 1
                elif modules[ext].get("name") != name:  # corridas anteriores usaban solo el nombre de la lista
                    self.pl.write("PATCH", self.pl.proj(self.pid, f"modules/{modules[ext]['id']}/"), {"name": name})
                    self.stats["módulos renombrados"] += 1
                self.module_by_list[lst["id"]] = modules[ext]["id"]

    def properties(self):
        existing = {p["external_id"]: p for p in self.pl.get(self.pl.mawesi(self.pid, "properties/"))
                    if p.get("external_source") == M.SOURCE}
        self.prop_by_field, self.option_ids = {}, {}
        fields = sorted(self.fields.values(), key=lambda f: f["name"].lower())
        if self.a.estimate:
            fields.append({"id": "time_estimate", "name": "Estimado (h)", "type": "number"})
        used = M.used_field_ids(self.tasks.values())
        for i, f in enumerate(fields):
            kind = M.FIELD_TYPES.get(f["type"], "text")
            prop = existing.get(f["id"])
            if prop is None and f["id"] not in used:
                self.stats["campos sin uso (no se crean)"] += 1
                continue
            if prop is None:
                body = {"name": f["name"][:120], "type": kind, "sort_order": (i + 1) * 1000,
                        "external_source": M.SOURCE, "external_id": f["id"],
                        "options": M.option_list(f) if kind in ("select", "multi_select") else []}
                try:
                    prop = self.pl.write("POST", self.pl.mawesi(self.pid, "properties/"), body)
                    self.stats["campos"] += 1
                except PlaneError as e:
                    self.warn("campo no creado", f"{f['name']}: {e}")
                    continue
            self.prop_by_field[f["id"]] = prop["id"]
            for o in prop.get("options", []):
                if o.get("external_id"):
                    self.option_ids[o["external_id"]] = o["id"]

    # ---------- 3. tareas ----------
    def home_cycle_and_module(self, t):
        lid = t["list"]["id"]
        cycle = self.cycle_by_list.get(lid)
        if cycle is None:
            for loc in t.get("locations", []):
                cycle = cycle or self.cycle_by_list.get(loc.get("id"))
        return cycle, self.module_by_list.get(lid)

    def issues(self):
        existing, self.parent_of = {}, {}
        for i in self.pl.all(self.pl.proj(self.pid, "issues/")):
            if i.get("external_source") == M.SOURCE:
                existing[i["external_id"]] = i["id"]
                self.parent_of[i["id"]] = i.get("parent")
        self.issue_by_task = {}
        self.new_issues = set()
        ordered = sorted(self.tasks.values(), key=lambda t: int(t.get("date_created") or 0))
        for n, t in enumerate(ordered, 1):
            if t["id"] in existing:
                self.issue_by_task[t["id"]] = existing[t["id"]]
                continue
            self.create_issue(t)
            if n % 200 == 0:
                self.log(f"  tareas {n}/{len(ordered)}")
        self.link_parents(ordered)

    def issue_body(self, t):
        assignees = [self.cu_user.get(a["id"]) for a in t.get("assignees", [])]
        start, due = M.ms_to_date(t.get("start_date")), M.ms_to_date(t.get("due_date"))
        if start and due and start > due:
            self.warn("fecha inicio > fecha fin (se descarta el inicio)", t["id"])
            start = None
        body = {
            "name": (t["name"] or "(sin título)")[:255],
            "description_html": M.description_html(t),
            "state": self.state_of(t),
            "priority": M.priority(t),
            "assignees": [a for a in assignees if a],
            "labels": self.labels_of(t),
            "start_date": start, "target_date": due,
            "external_source": M.SOURCE, "external_id": t["id"],
            "created_at": M.ms_to_iso(t.get("date_created")),
            "created_by": self.cu_user.get((t.get("creator") or {}).get("id")) or self.me,
        }
        if len(assignees) != len(body["assignees"]):
            self.warn("asignado sin cuenta en MWSTASKS", t["id"])
        return body

    def create_issue(self, t):
        try:
            issue = self.pl.write("POST", self.pl.proj(self.pid, "issues/"), self.issue_body(t))
            self.issue_by_task[t["id"]] = issue["id"]
            self.new_issues.add(t["id"])
            self.stats["tareas"] += 1
        except PlaneError as e:
            if e.code == 409 and e.json().get("id"):
                self.issue_by_task[t["id"]] = e.json()["id"]
            else:
                self.warn("tarea no creada", f"{t['id']}: {e}")

    def link_parents(self, ordered):
        # Subtareas: el padre se pone después, cuando ya existen todas. Revisa todas (no solo las nuevas)
        # para completar una corrida anterior que se cortó.
        for t in ordered:
            if t.get("parent") and t["id"] in self.issue_by_task:
                parent = self.issue_by_task.get(t["parent"])
                if parent and self.parent_of.get(self.issue_by_task[t["id"]]) == parent:
                    continue
                if parent:
                    self.pl.write("PATCH", self.pl.proj(self.pid, f"issues/{self.issue_by_task[t['id']]}/"), {"parent": parent})
                    self.stats["subtareas enlazadas"] += 1
                else:
                    self.warn("padre fuera del alcance migrado", t["id"])

    def relations(self):
        # "Linked tasks" y campos de relación. Las que apuntan a otro proyecto todavía sin migrar quedan
        # "sin_tarea"; las completa la próxima corrida (o el --prune de la copia incremental).
        pairs = M.relation_pairs(self.tasks.values())
        if not pairs:
            return
        for key, n in send_relations(self.pl, pairs).items():
            if n:
                self.stats[f"relaciones {key.replace('_', ' ')}"] += n

    def _add_missing(self, kind, container_id, wanted):
        path = self.pl.proj(self.pid, f"{kind}s/{container_id}/{kind}-issues/")
        have = {x.get("id") or x.get("issue") for x in self.pl.all(path)}
        missing = [i for i in wanted if i not in have]
        for k in range(0, len(missing), 100):
            self.pl.write("POST", path, {"issues": missing[k:k + 100]})
        return len(missing)

    def grouping(self):
        """Ciclos y módulos. Revisa todas las tareas y agrega solo las que faltan (idempotente)."""
        by_cycle, by_module = collections.defaultdict(list), collections.defaultdict(list)
        for tid, iid in self.issue_by_task.items():
            if tid not in self.tasks:  # padre buscado aparte en la copia incremental
                continue
            cycle, module = self.home_cycle_and_module(self.tasks[tid])
            if cycle:
                by_cycle[cycle].append(iid)
            if module:
                by_module[module].append(iid)
        for cid, info in self.cycle_info.items():
            ids = by_cycle.get(cid, [])
            if ids and info["has_dates"] and info["end"] and info["end"] < M.today():
                self.warn("ciclo ya cerrado: no se le pueden agregar tareas", cid)
            elif ids:
                self.stats["tareas en ciclos"] += self._add_missing("cycle", cid, ids)
            if not info["has_dates"] and info["start"] and info["end"]:
                self.pl.write("PATCH", self.pl.proj(self.pid, f"cycles/{cid}/"),
                              {"start_date": info["start"], "end_date": info["end"]})
                self.stats["ciclos con fechas"] += 1
        for mid, ids in by_module.items():
            self.stats["tareas en módulos"] += self._add_missing("module", mid, ids)

    def values(self):
        # Para todas las tareas: MWSTASKS ignora los valores que no cambian, así que repetir es seguro.
        for tid in self.issue_by_task:
            if tid not in self.tasks:
                continue
            t, values = self.tasks[tid], {}
            for cf in t.get("custom_fields", []):
                pid = self.prop_by_field.get(cf["id"])
                if not pid:
                    continue
                v, warn = M.field_value(cf, cf.get("value"), self.option_ids, self.user_by_email)
                if warn:
                    self.warn(f"valor de campo: {warn.split(':')[0]}", f"{tid} {cf['name']}: {warn}")
                if v is not None:
                    values[pid] = v
            if self.a.estimate and "time_estimate" in self.prop_by_field and t.get("time_estimate") is not None:
                hours = M.estimate_hours(t["time_estimate"])
                if hours is None and t["time_estimate"]:
                    self.warn("estimado menor a 1 minuto en ClickUp (se deja vacío)", tid)
                values[self.prop_by_field["time_estimate"]] = hours  # None borra un valor viejo
            if not values:
                continue
            path = self.pl.mawesi(self.pid, f"issues/{self.issue_by_task[tid]}/property-values/")
            try:
                self.pl.write("PATCH", path, {"values": values})
                self.stats["tareas con campos revisadas"] += 1
            except PlaneError:
                for k, v in values.items():  # todo-o-nada falló: cargar de a uno para salvar los válidos
                    try:
                        self.pl.write("PATCH", path, {"values": {k: v}})
                    except PlaneError as e:
                        self.warn("valor rechazado", f"{tid}: {e}")

    def comments(self):
        names = {}
        for n, tid in enumerate(sorted(self.issue_by_task), 1):
            if n < self.a.comments_start:  # retomar una corrida cortada (el orden es siempre el mismo)
                continue
            iid = self.issue_by_task[tid]
            for c in self.cu.comments(tid):
                for item in [c] + (self.cu.get(f"/comment/{c['id']}/reply").get("comments", []) if int(c.get("reply_count") or 0) else []):
                    user = item.get("user") or {}
                    names[user.get("id")] = user.get("username") or user.get("email") or "?"
                    body = {"comment_html": M.comment_html(item, names[user.get("id")]),
                            "external_source": M.SOURCE, "external_id": str(item["id"]),
                            "created_at": M.ms_to_iso(item.get("date")),
                            "created_by": self.user_by_email.get((user.get("email") or "").lower()) or self.me}
                    self.post_comment(iid, body)
            if not self.a.skip_attachments:
                self.attachments(tid, iid)
            if n % 250 == 0:
                self.log(f"  comentarios y adjuntos: {n}/{len(self.issue_by_task)} tareas revisadas")

    def post_comment(self, iid, body):
        try:
            self.pl.write("POST", self.pl.proj(self.pid, f"issues/{iid}/comments/"), body)
            self.stats["comentarios"] += 1
            return True
        except PlaneError as e:
            if e.code != 409:
                self.warn("comentario no creado", f"{iid}: {e}")
            return False

    def attachments(self, tid, iid):
        files = self.cu.task(tid).get("attachments") or []
        if not files:
            return
        path = self.pl.proj(self.pid, f"issues/{iid}/issue-attachments/")
        done = {a.get("external_id") for a in self.pl.get(path) or [] if a.get("external_source") == M.SOURCE}
        limit = self.file_limit
        for a in files:
            ext = str(a["id"])
            if ext in done:
                continue
            name, mime = M.attachment_name(a), M.attachment_mime(a)
            if int(a.get("size") or 0) > limit:
                self.warn(f"adjunto mayor al límite de {limit // 1048576} MB (no se copia)", f"{tid}: {name} ({int(a['size']) // 1048576} MB)")
                continue
            try:
                content = self.cu.download(a["url"], limit)
            except Exception as e:  # noqa: BLE001 - un adjunto roto no frena la migración
                self.warn("adjunto que no se pudo bajar de ClickUp", f"{tid}: {name}: {e}")
                continue
            body = {"name": name, "type": mime, "size": len(content), "external_source": M.SOURCE, "external_id": ext}
            try:
                created = self.pl.write("POST", path, body)
            except PlaneError as e:
                if e.code == 409 and e.json().get("id"):
                    # Quedó creado pero sin archivo (corrida cortada): se borra y se vuelve a crear.
                    self.pl.write("DELETE", f"{path}{e.json()['id']}/")
                    created = self.pl.write("POST", path, body)
                elif e.code == 400 and "type" in e.body.lower() and mime != "application/octet-stream":
                    body["type"] = mime = "application/octet-stream"
                    created = self.pl.write("POST", path, body)
                else:
                    self.warn("adjunto rechazado por MWSTASKS", f"{tid}: {name}: {e}")
                    continue
            try:
                self.pl.upload_presigned(created["upload_data"], name, content, mime)
                self.pl.write("PATCH", f"{path}{created['asset_id']}/", {})
                self.stats["adjuntos"] += 1
                self.stats["MB de adjuntos"] = round(self.stats["MB de adjuntos"] + len(content) / 1048576, 1)
            except PlaneError as e:
                self.warn("adjunto que no se pudo subir", f"{tid}: {name}: {e}")

    def worklogs(self):
        info = self.cu.get("/team")["teams"][0]
        team = self.a.team or info["id"]
        # Miembros actuales + todas las personas vistas en las tareas: ClickUp solo devuelve horas de quien se nombra,
        # y los ex empleados tienen años de horas (p. ej. TQ desde 2021).
        cu_ids = {m["user"]["id"] for m in info["members"]} | {k for k in self.cu_user if isinstance(k, int) and k > 0}
        start = int(time.mktime(time.strptime(self.a.time_from, "%Y-%m-%d")) * 1000)
        end = int(time.time() * 1000)
        entries, ids = {}, sorted(cu_ids)
        for k in range(0, len(ids), 10):
            for e in self.cu.get(f"/team/{team}/time_entries", start_date=start, end_date=end, space_id=self.a.space,
                                 assignee=",".join(map(str, ids[k:k + 10])), include_task_tags="false").get("data", []):
                entries[e["id"]] = e
        entries = [e for e in entries.values() if not self.skip_entry(e)]
        by_issue = collections.defaultdict(list)
        self.copied_entries = []
        for e in entries:
            tid = (e.get("task") or {}).get("id")
            iid = self.issue_by_task.get(tid) or (self.route_task(tid) if tid else None)
            if iid:
                by_issue[iid].append(e)
            else:
                self.warn("hora fuera del alcance migrado", e.get("id"))
                self.copied_entries.append(e["id"])  # no se vuelve a revisar
        self.stats["horas leídas"] = len(entries)
        for iid, rows in by_issue.items():
            done = {w["description"].split("]")[0] + "]" for w in self.pl.get(self.pl.mawesi(self.pid, f"issues/{iid}/worklogs/")) if (w.get("description") or "").startswith("[clickup:")}
            for e in rows:
                email = ((e.get("user") or {}).get("email") or "").lower()
                member = self.user_by_email.get(email)
                if int(e["duration"]) < 0:  # cronómetro corriendo: se copia cuando se detenga
                    continue
                minutes = max(1, round(int(e["duration"]) / 60000))
                for k, chunk in enumerate(M.split_minutes(minutes)):
                    tag = f"[clickup:{e['id']}{'#' + str(k) if k else ''}]"
                    if tag in done:
                        continue
                    note = (e.get("description") or "").strip()
                    if not member:
                        note = f"Registrado por {email or '?'} en ClickUp. {note}"
                    body = {"duration_minutes": chunk, "date": M.ms_to_date(e["start"]),
                            "description": f"{tag} {note}".strip()[:2000]}
                    if member:
                        body["member"] = member
                    try:
                        self.pl.write("POST", self.pl.mawesi(self.pid, f"issues/{iid}/worklogs/"), body)
                        self.stats["horas migradas"] += 1
                        self.stats["minutos migrados"] += chunk
                    except PlaneError as err:
                        self.warn("hora no migrada", f"{e['id']}: {err}")
                        break
                else:
                    self.copied_entries.append(e["id"])

    # Ganchos para la copia incremental (sync.py): la migración completa no salta ni busca nada aparte.
    def skip_entry(self, entry):
        return False

    def route_task(self, task_id):
        return None

    def setup(self):
        self.me = self.pl.get("/api/v1/users/me/")["id"]
        # Nunca más grande que lo que acepta la instancia: si no, el proxy corta la subida.
        self.file_limit = min(self.a.max_file_mb * 1024 * 1024, self.pl.file_size_limit())
        self.log(f"Límite de adjuntos: {self.file_limit // 1048576} MB")

    def report(self):
        return {"proyecto": self.pid, "creado": dict(self.stats), "avisos": dict(self.warnings),
                "ejemplos": dict(self.samples), "llamadas": {"clickup": self.cu.calls, "mwstasks": self.pl.calls}}

    def run(self):
        self.read_clickup()
        self.setup()
        self.people()
        self.project()
        self.states(); self.labels(); self.cycles_and_modules(); self.properties()
        self.log("Estructura lista. Creando tareas…")
        self.issues(); self.grouping(); self.relations()
        self.log("Cargando valores de campos…"); self.values()
        if not self.a.skip_comments:
            self.log("Copiando comentarios y adjuntos…"); self.comments()
        if not self.a.skip_time:
            self.log("Copiando horas…"); self.worklogs()
        report = self.report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--space", required=True)
    ap.add_argument("--folders", default="")
    ap.add_argument("--team", default="")
    ap.add_argument("--url", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--project-name", required=True)
    ap.add_argument("--identifier", required=True)
    ap.add_argument("--time-from", default="2020-01-01")
    ap.add_argument("--estimate", action="store_true", help="copiar el tiempo estimado como campo 'Estimado (h)'")
    ap.add_argument("--skip-comments", action="store_true", help="tampoco copia adjuntos (van en el mismo recorrido)")
    ap.add_argument("--skip-attachments", action="store_true")
    ap.add_argument("--max-file-mb", type=int, default=20, help="adjuntos más grandes se saltan (igual que FILE_SIZE_LIMIT)")
    ap.add_argument("--skip-time", action="store_true")
    ap.add_argument("--comments-start", type=int, default=1, help="retomar comentarios y adjuntos desde la tarea N")
    a = ap.parse_args()
    cu = ClickUp(os.environ["CLICKUP_TOKEN"])
    pl = Plane(a.url, os.environ["MWSTASKS_TOKEN"], a.workspace)
    Migration(cu, pl, a).run()


if __name__ == "__main__":
    sys.exit(main())
