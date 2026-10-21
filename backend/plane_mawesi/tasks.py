# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Tareas de Celery MAWESI (Plane las descubre con app.autodiscover_tasks). El horario está en la base
(django_celery_beat), cargado por las migraciones 0006 (repeticiones) y 0008 (repositorios de código)."""
from celery import shared_task

from plane_mawesi import recurrence


@shared_task
def run_recurrences():
    return recurrence.run_due()


@shared_task
def run_automations(issue_id, project_id, trigger, value):
    from plane_mawesi import automations

    return automations.run(issue_id, project_id, trigger, value)


@shared_task
def sync_code_repos():
    from plane_mawesi import code

    return code.sync_all()


@shared_task
def run_dependencies(job, issue_id, actor_id):
    from plane_mawesi import dependencies

    return {"unblock": dependencies.unblock, "reschedule": dependencies.reschedule}[job](issue_id, actor_id)
