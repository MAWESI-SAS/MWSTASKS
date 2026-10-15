# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from plane.db.models.project import ProjectBaseModel

MAX_MINUTES_PER_ENTRY = 24 * 60


class Worklog(ProjectBaseModel):
    """Tiempo registrado en un work item. Tabla propia (prefijo mawesi_): Plane nunca la toca.

    `member` es a quién se le imputan las horas (por defecto, quien registra). `created_by` (de
    BaseModel) es quién hizo el registro: un admin puede cargar horas de otra persona.
    """

    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="mawesi_worklogs")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mawesi_worklogs")
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_MINUTES_PER_ENTRY)]
    )
    date = models.DateField()
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "mawesi_worklogs"
        ordering = ("-date", "-created_at")
        indexes = [
            models.Index(fields=["issue"], name="mawesi_wl_issue_idx"),
            models.Index(fields=["workspace", "member", "date"], name="mawesi_wl_ws_member_date_idx"),
            models.Index(fields=["project", "date"], name="mawesi_wl_project_date_idx"),
        ]

    def __str__(self):
        return f"{self.issue_id} · {self.member_id} · {self.duration_minutes} min · {self.date}"


class Timer(ProjectBaseModel):
    """Cronómetro andando (como el ▶ de ClickUp). Uno por persona y workspace; al pararlo se vuelve un Worklog."""

    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="mawesi_timers")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mawesi_timers")
    started_at = models.DateTimeField()
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "mawesi_timers"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "member"], condition=models.Q(deleted_at__isnull=True), name="mawesi_timer_one_per_member"
            ),
        ]

    def __str__(self):
        return f"{self.member_id} · {self.issue_id} · desde {self.started_at:%Y-%m-%d %H:%M}"


class PropertyType(models.TextChoices):
    TEXT = "text", "Texto"
    URL = "url", "URL"
    NUMBER = "number", "Número"
    DATE = "date", "Fecha"
    CHECKBOX = "checkbox", "Sí/No"
    SELECT = "select", "Selección única"
    MULTI_SELECT = "multi_select", "Selección múltiple"
    MEMBER = "member", "Persona"


OPTION_TYPES = (PropertyType.SELECT, PropertyType.MULTI_SELECT)


class Property(ProjectBaseModel):
    """Campo propio de un proyecto (equivale a un custom field de lista en ClickUp)."""

    name = models.CharField(max_length=120)
    type = models.CharField(max_length=20, choices=PropertyType.choices)
    description = models.TextField(blank=True, default="")
    sort_order = models.FloatField(default=65535)
    is_active = models.BooleanField(default=True)
    # Para la migración desde ClickUp (id del custom field), y evitar duplicados al re-importar.
    external_source = models.CharField(max_length=40, blank=True, default="")
    external_id = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        db_table = "mawesi_properties"
        ordering = ("sort_order", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"], condition=models.Q(deleted_at__isnull=True), name="mawesi_prop_unique_name"
            ),
        ]

    def __str__(self):
        return f"{self.project_id} · {self.name} ({self.type})"


class PropertyOption(ProjectBaseModel):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="options")
    name = models.CharField(max_length=120)
    color = models.CharField(max_length=20, blank=True, default="")
    sort_order = models.FloatField(default=65535)
    external_id = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        db_table = "mawesi_property_options"
        ordering = ("sort_order", "created_at")


class PropertyValue(ProjectBaseModel):
    """Valor de un campo en un work item. `value` es JSON validado según el tipo (ver services.properties)."""

    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="mawesi_property_values")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="values")
    value = models.JSONField(null=True)

    class Meta:
        db_table = "mawesi_property_values"
        constraints = [
            models.UniqueConstraint(
                fields=["issue", "property"], condition=models.Q(deleted_at__isnull=True), name="mawesi_value_unique"
            ),
        ]
        indexes = [models.Index(fields=["project", "property"], name="mawesi_value_proj_prop_idx")]
