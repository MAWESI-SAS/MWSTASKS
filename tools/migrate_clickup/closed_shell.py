# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Pone la fecha real de cierre (de `closed_dates.py`) en las tareas migradas cerradas. Se corre DENTRO del api:

  docker cp closed.json <api>:/tmp/closed.json
  docker exec -i -e SLUG=mawesi -e CLOSED=/tmp/closed.json <api> python manage.py shell < closed_shell.py

Solo toca tareas de ClickUp en un estado "completed". Usa update() (sin señales ni historial): es una corrección de
datos de la migración, no un cambio de la tarea. Idempotente.
"""
import datetime as dt
import json
import os

from plane.db.models import Issue

closed = json.load(open(os.environ["CLOSED"]))
qs = Issue.issue_objects.filter(workspace__slug=os.environ["SLUG"], external_source="clickup",
                                external_id__in=list(closed), state__group="completed")
fixed = same = 0
for issue_id, ext, current in qs.values_list("id", "external_id", "completed_at"):
    real = dt.datetime.fromtimestamp(closed[ext] / 1000, tz=dt.timezone.utc)
    if current and abs((current - real).total_seconds()) < 60:
        same += 1
        continue
    Issue.objects.filter(pk=issue_id).update(completed_at=real)
    fixed += 1
print(json.dumps({"corregidas": fixed, "ya estaban bien": same, "fechas leídas": len(closed)}))
