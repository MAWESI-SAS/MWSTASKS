# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Tareas de Celery MAWESI (Plane las descubre con app.autodiscover_tasks). El horario está en la base
(django_celery_beat), cargado por la migración 0006."""
from celery import shared_task

from plane_mawesi import recurrence


@shared_task
def run_recurrences():
    return recurrence.run_due()
