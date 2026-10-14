# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Inventario (solo lectura) de lo que se va a migrar desde un espacio de ClickUp.

Uso: CLICKUP_TOKEN=... python3 -m tools.migrate_clickup.inventory <space_id> [--folders "Product,Sprints"]
"""
import argparse
import collections
import os

from tools.migrate_clickup.clickup import ClickUp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("space_id")
    ap.add_argument("--folders", default="", help="carpetas a incluir, separadas por coma (vacío = todas)")
    a = ap.parse_args()
    cu = ClickUp(os.environ["CLICKUP_TOKEN"])
    wanted = {f.strip() for f in a.folders.split(",") if f.strip()}
    folders = [f for f in cu.folders(a.space_id) if not wanted or f["name"] in wanted]
    totals = collections.Counter()
    statuses, fields, members = collections.Counter(), {}, {}
    for f in folders:
        print(f"\n## Carpeta: {f['name']} ({len(f['lists'])} listas)")
        for lst in f["lists"]:
            tasks = list(cu.tasks(lst["id"]))
            subs = sum(1 for t in tasks if t.get("parent"))
            closed = sum(1 for t in tasks if t["status"]["type"] == "closed")
            com = sum(int(t.get("comment_count") or 0) for t in tasks) if tasks and "comment_count" in tasks[0] else None
            atts = sum(len(t.get("attachments") or []) for t in tasks)
            for t in tasks:
                statuses[(t["status"]["status"], t["status"]["type"])] += 1
                for m in t.get("assignees", []):
                    members[m["id"]] = m.get("email") or m.get("username")
            for fd in cu.custom_fields(lst["id"]):
                fields[fd["id"]] = (fd["name"], fd["type"])
            totals.update(listas=1, tareas=len(tasks), subtareas=subs, cerradas=closed, adjuntos=atts)
            print(f"  - {lst['name']}: {len(tasks)} tareas ({subs} subtareas, {closed} cerradas, {atts} adjuntos)")
    print("\n## Totales:", dict(totals))
    print("## Estados:", {f"{s} [{t}]": n for (s, t), n in statuses.most_common()})
    print(f"## Campos propios ({len(fields)}):", sorted({n for n, _ in fields.values()}))
    print(f"## Personas asignadas ({len(members)}):", len(members))
    print("## Llamadas a ClickUp:", cu.calls)


if __name__ == "__main__":
    main()
