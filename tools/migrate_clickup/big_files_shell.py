# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Deja un comentario en cada tarea migrada cuyo adjunto no entró por tamaño, con dónde quedó en el respaldo.
Se corre DENTRO del api (como `closed_shell.py`):

  docker cp big_files.json <api>:/tmp/big_files.json
  docker exec -i -e SLUG=mawesi -e FILES=/tmp/big_files.json -e ACTOR=<email> -e WHERE="mwsws15:/ruta/del/respaldo" \
    <api> python manage.py shell < big_files_shell.py

Idempotente: si la tarea ya tiene el comentario de ese archivo, no lo repite.
"""
import html
import json
import os

from crum import impersonate

from plane.db.models import Issue, IssueComment, User

MARK = "Respaldo de ClickUp"
SOURCE = "clickup-backup"  # external_id = ruta del archivo en el respaldo
files = json.load(open(os.environ["FILES"]))
actor = User.objects.get(email=os.environ["ACTOR"])
where = os.environ["WHERE"].rstrip("/")
issues = {i.external_id: i for i in Issue.issue_objects.filter(
    workspace__slug=os.environ["SLUG"], external_source="clickup", external_id__in={f["task"] for f in files})}
added = skipped = missing = 0
with impersonate(actor):
    for f in files:
        issue = issues.get(f["task"])
        if issue is None:
            missing += 1
            continue
        name = html.escape(f["name"])
        if IssueComment.objects.filter(issue=issue, external_source=SOURCE, external_id=f["path"][:255]).exists():
            skipped += 1
            continue
        text = (f"{MARK}: el adjunto «{f['name']}» ({f['mb']} MB) no entró en MWSTASKS por tamaño. "
                f"Está guardado en {where}/{f['path']}")
        IssueComment.objects.create(
            issue=issue, project_id=issue.project_id, workspace_id=issue.workspace_id, actor=actor,
            comment_html=f"<p><strong>{MARK}</strong>: el adjunto «{name}» ({f['mb']} MB) no entró en MWSTASKS por tamaño. "
                         f"Está guardado en <code>{html.escape(where)}/{html.escape(f['path'])}</code></p>",
            comment_stripped=text, external_source=SOURCE, external_id=f["path"][:255],
        )
        added += 1
print(json.dumps({"comentarios nuevos": added, "ya estaban": skipped, "tareas no migradas": missing}))
