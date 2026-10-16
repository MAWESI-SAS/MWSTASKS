# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Fecha real de cierre de las tareas de ClickUp (SOLO LECTURA) -> JSON {task_id: ms}, para `closed_shell.py`.

Las tareas migradas ya cerradas quedaron con `completed_at` = día de la migración (Plane lo pone al crear la tarea
en un estado "completed"). El SLA y los reportes necesitan la fecha real.

  CLICKUP_TOKEN=... python -m tools.migrate_clickup.closed_dates --config sync.json --out closed.json
"""
import argparse
import json
import os

from .clickup import ClickUp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--team", default="30902916")
    a = ap.parse_args()
    cu = ClickUp(os.environ["CLICKUP_TOKEN"])
    spaces = [p["space"] for p in json.load(open(a.config))["projects"]]
    closed = {}
    for t in cu.team_tasks(a.team, spaces):
        when = t.get("date_closed") or t.get("date_done")
        if when:
            closed[t["id"]] = int(when)
    with open(a.out, "w") as f:
        json.dump(closed, f)
    print(json.dumps({"tareas cerradas": len(closed), "llamadas ClickUp": cu.calls}))


if __name__ == "__main__":
    main()
