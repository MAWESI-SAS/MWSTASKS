# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Vistas guardadas parecidas a las de ClickUp, en cada proyecto del workspace. Se corre DENTRO del contenedor api:

  docker exec -i -e SLUG=mawesi -e OWNER=<email-admin> <api> python manage.py shell < views_shell.py

Públicas (las ve todo el proyecto), a nombre de OWNER. Idempotente: si la vista ya existe (mismo nombre), solo
corrige su filtro de estados. Ojo: Plane guarda los valores de un filtro "__in" como texto separado por comas.
La API v1 de Plane no permite crear vistas; por eso va por shell.
"""
import os

from plane.db.models import IssueView, Project, User
from plane.db.models.view import get_default_display_filters

OPEN = ["backlog", "unstarted", "started"]
CLOSED = ["completed", "cancelled"]
VIEWS = [
    # nombre, layout, agrupar por, grupos de estado
    ("Abiertas por estado", "list", "state", OPEN),
    ("Tablero", "kanban", "state", OPEN),
    ("Por responsable", "kanban", "assignees", OPEN),
    ("Calendario", "calendar", None, OPEN),
    ("Gantt", "gantt_chart", None, OPEN),
    ("Cerradas", "list", None, CLOSED),
]

owner = User.objects.get(email=os.environ["OWNER"])
created = fixed = 0
for project in Project.objects.filter(workspace__slug=os.environ["SLUG"]):
    have = {v.name: v for v in IssueView.objects.filter(project=project)}
    for i, (name, layout, group_by, groups) in enumerate(VIEWS):
        rich = {"state_group__in": ",".join(groups)}
        if name in have:
            if have[name].rich_filters != rich and have[name].owned_by_id == owner.id:
                have[name].rich_filters = rich
                have[name].save(update_fields=["rich_filters"])
                fixed += 1
            continue
        IssueView.objects.create(
            name=name, project=project, workspace_id=project.workspace_id, owned_by=owner, created_by=owner,
            access=1, sort_order=(i + 1) * 1000,
            filters={"state_group": groups},
            rich_filters=rich,
            display_filters={**get_default_display_filters(), "layout": layout, "group_by": group_by,
                             "order_by": "-updated_at" if groups == CLOSED else "sort_order"},
        )
        created += 1
print(f"vistas creadas: {created}, corregidas: {fixed}")
