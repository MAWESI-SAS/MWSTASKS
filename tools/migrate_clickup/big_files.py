# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Adjuntos de ClickUp que no entraron en MWSTASKS por tamaño, buscados en el respaldo (`backup.py`).

  python -m tools.migrate_clickup.big_files --backup <carpeta> --min-mb 100 > big_files.json

Salida: [{"task", "name", "mb", "path"}], con `path` relativo a la carpeta del respaldo. La usa `big_files_shell.py`
para dejar en cada tarea un comentario con dónde está el archivo.
"""
import argparse
import glob
import json
import os

from .backup import safe_name


def find(backup: str, min_mb: int) -> list[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(backup, "tasks", "*", "*.json"))):
        with open(path) as f:
            task = json.load(f)["task"]
        for a in task.get("attachments") or []:
            size = int(a.get("size") or 0)
            if size <= min_mb * 1048576:
                continue
            rel = os.path.join("files", task["id"], f"{a['id']}-{safe_name(a.get('title') or a['url'].rsplit('/', 1)[-1])}")
            out.append({"task": task["id"], "name": a.get("title") or "", "mb": round(size / 1048576),
                        "path": rel, "saved": os.path.exists(os.path.join(backup, rel))})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backup", required=True)
    ap.add_argument("--min-mb", type=int, default=100, help="igual que el límite de adjuntos de MWSTASKS")
    a = ap.parse_args()
    print(json.dumps(find(a.backup, a.min_mb), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
