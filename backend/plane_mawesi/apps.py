# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
from django.apps import AppConfig
from django.db.models.signals import post_save


class PlaneMawesiConfig(AppConfig):
    """Funciones MAWESI sobre Plane CE (horas, campos, SLA, plantillas, repetición, reglas). Vive fuera del código
    de Plane."""

    name = "plane_mawesi"
    label = "mawesi"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from plane.db.models import IssueActivity

        from celery.signals import task_postrun, task_prerun

        from plane_mawesi.automations import on_activity, on_task_postrun, on_task_prerun

        # Reglas automáticas: se disparan con el historial de Plane (ver automations.py).
        post_save.connect(on_activity, sender=IssueActivity, dispatch_uid="mawesi-automations")
        task_prerun.connect(on_task_prerun, weak=False, dispatch_uid="mawesi-automations-prerun")
        task_postrun.connect(on_task_postrun, weak=False, dispatch_uid="mawesi-automations-postrun")
