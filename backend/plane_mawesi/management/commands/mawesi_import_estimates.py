# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Copia un campo propio numérico en horas (el "Estimado (h)" que vino de ClickUp) al estimado de MWSTASKS.

  docker compose exec -T mwstasks-api python manage.py mawesi_import_estimates --workspace mawesi [--property "Estimado (h)"]

Solo llena las tareas que todavía no tienen estimado: lo que alguien ya cargó en MWSTASKS no se pisa. No toca el campo
propio ni escribe historial (es una copia de datos viejos). Se puede repetir.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from plane.db.models import Issue

from plane_mawesi.estimates import MAX_MINUTES
from plane_mawesi.models import IssueEstimate, Property, PropertyType, PropertyValue

BATCH = 1000


class Command(BaseCommand):
    help = "Copia un campo propio en horas al estimado de las tareas que no lo tienen."

    def add_arguments(self, parser):
        parser.add_argument("--workspace", required=True)
        parser.add_argument("--property", default="Estimado (h)")

    def handle(self, *args, workspace, property, **options):
        props = Property.objects.filter(workspace__slug=workspace, name=property, type=PropertyType.NUMBER)
        if not props.exists():
            raise CommandError(f"No hay un campo numérico «{property}» en {workspace}")
        for prop in props.select_related("project"):
            rows = PropertyValue.objects.filter(property=prop, issue__in=Issue.issue_objects.all()).exclude(value=None)
            have = set(IssueEstimate.objects.filter(project_id=prop.project_id).values_list("issue_id", flat=True))
            new, skipped = [], 0
            for v in rows.values("issue_id", "value"):
                try:
                    minutes = round(float(v["value"]) * 60)
                except (TypeError, ValueError):
                    skipped += 1
                    continue
                if v["issue_id"] in have or not 0 < minutes <= MAX_MINUTES:
                    skipped += 1
                    continue
                new.append(IssueEstimate(issue_id=v["issue_id"], project_id=prop.project_id, workspace_id=prop.workspace_id,
                                         original_minutes=minutes))
            with transaction.atomic():
                IssueEstimate.objects.bulk_create(new, batch_size=BATCH)
            self.stdout.write(f"{prop.project.identifier}: {len(new)} estimados copiados, {skipped} saltados")
