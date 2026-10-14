# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
from django.apps import AppConfig


class PlaneMawesiConfig(AppConfig):
    """Funciones MAWESI sobre Plane CE: horas y campos propios. Vive fuera del código de Plane."""

    name = "plane_mawesi"
    label = "mawesi"
    default_auto_field = "django.db.models.BigAutoField"
