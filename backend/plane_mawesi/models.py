# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from plane.db.models.project import ProjectBaseModel
from plane.db.models.workspace import WorkspaceBaseModel

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


def default_sla_hours():
    return {"urgent": 4, "high": 8, "medium": 16, "low": 40, "none": 40}


def default_workdays():
    return [0, 1, 2, 3, 4]


class SlaPolicy(ProjectBaseModel):
    """Plazo de resolución por prioridad, en horas hábiles. Una por proyecto; si tiene módulo, aplica solo a sus
    work items (p. ej. "Soporte - TQ / Incidentes"). El cálculo vive en plane_mawesi/sla.py."""

    module = models.ForeignKey("db.Module", on_delete=models.SET_NULL, null=True, blank=True, related_name="mawesi_sla")
    hours = models.JSONField(default=default_sla_hours)  # {"urgent": 4, "high": 8, ...}
    timezone = models.CharField(max_length=64, default="America/Bogota")
    work_start = models.TimeField(default="08:00")
    work_end = models.TimeField(default="18:00")
    workdays = models.JSONField(default=default_workdays)  # lunes=0
    colombia_holidays = models.BooleanField(default=True)

    class Meta:
        db_table = "mawesi_sla_policies"
        constraints = [
            models.UniqueConstraint(
                fields=["project"], condition=models.Q(deleted_at__isnull=True), name="mawesi_sla_one_per_project"
            ),
        ]

    def __str__(self):
        return f"SLA {self.project_id}"


class TaskTemplate(ProjectBaseModel):
    """Plantilla de tarea: prioridad, lista, responsables y checklist de la tarea + subtareas ya armadas
    (p. ej. las fases de un requerimiento de TQ). Se aplica con plane_mawesi/templates.py."""

    name = models.CharField(max_length=120)
    priority = models.CharField(max_length=16, default="none")
    module = models.ForeignKey("db.Module", on_delete=models.SET_NULL, null=True, blank=True, related_name="mawesi_templates")
    assignee_ids = models.JSONField(default=list)
    checklist = models.JSONField(default=list)  # ["PR creado", ...]
    subtasks = models.JSONField(default=list)  # [{"name": "Diseño", "priority": "none", "checklist": [...]}]
    # "Diseño - <nombre de la tarea>", como se nombraban las fases en ClickUp.
    add_parent_name = models.BooleanField(default=True)

    class Meta:
        db_table = "mawesi_task_templates"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"], condition=models.Q(deleted_at__isnull=True), name="mawesi_template_unique_name"
            ),
        ]

    def __str__(self):
        return self.name


class RecurrenceFrequency(models.TextChoices):
    DAILY = "daily", "Cada día"
    WEEKDAYS = "weekdays", "Cada día hábil"
    WEEKLY = "weekly", "Cada semana"
    MONTHLY = "monthly", "Cada mes"


class RecurrenceTrigger(models.TextChoices):
    COMPLETE = "complete", "Al completarla"
    SCHEDULE = "schedule", "En la fecha de vencimiento"


class Recurrence(ProjectBaseModel):
    """Tarea que se repite (como en ClickUp). `issue` es la ocurrencia vigente: cuando se completa (o llega su
    vencimiento, según `trigger`) se crea la siguiente y la regla pasa a ella. Lo corre plane_mawesi/tasks.py."""

    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="mawesi_recurrences")
    frequency = models.CharField(max_length=16, choices=RecurrenceFrequency.choices)
    interval = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(30)])
    trigger = models.CharField(max_length=16, choices=RecurrenceTrigger.choices, default=RecurrenceTrigger.COMPLETE)
    occurrences = models.PositiveIntegerField(default=0)  # cuántas ya creó

    class Meta:
        db_table = "mawesi_recurrences"
        constraints = [
            models.UniqueConstraint(fields=["issue"], condition=models.Q(deleted_at__isnull=True), name="mawesi_recurrence_one_per_issue"),
        ]

    def __str__(self):
        return f"{self.frequency}×{self.interval} {self.issue_id}"


class AutomationTrigger(models.TextChoices):
    CREATED = "created", "Se crea una tarea"
    ADDED_TO_LIST = "added_to_list", "Una tarea entra a una lista"
    STATE = "state", "Cambia el estado a"
    PRIORITY = "priority", "Cambia la prioridad a"


def default_actions():
    return {}


class Automation(ProjectBaseModel):
    """Regla "Cuando <trigger> → <acciones>" (como las automatizaciones de ClickUp). Se dispara con el historial de
    Plane (IssueActivity), así funciona igual desde la web, la API o el tablero. Ver plane_mawesi/automations.py."""

    name = models.CharField(max_length=120)
    enabled = models.BooleanField(default=True)
    trigger = models.CharField(max_length=20, choices=AutomationTrigger.choices)
    trigger_value = models.CharField(max_length=64, blank=True, default="")  # id de estado/lista o prioridad
    module = models.ForeignKey("db.Module", on_delete=models.CASCADE, null=True, blank=True, related_name="mawesi_automations")
    # {"assignee_ids": [...], "state_id": "...", "priority": "...", "label_ids": [...], "due_in_days": 2, "template_id": "..."}
    actions = models.JSONField(default=default_actions)
    runs = models.PositiveIntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mawesi_automations"
        ordering = ["created_at"]

    def __str__(self):
        return self.name


class IssueEstimate(ProjectBaseModel):
    """Estimado y restante en horas de un work item (Original Estimate / Remaining Work de Azure DevOps). Lo hecho
    (Completed Work) no se guarda: es la suma de sus Worklog. `remaining_minutes` vacío = estimado − hecho."""

    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="mawesi_estimates")
    original_minutes = models.PositiveIntegerField(null=True, blank=True)
    remaining_minutes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "mawesi_issue_estimates"
        constraints = [
            models.UniqueConstraint(fields=["issue"], condition=models.Q(deleted_at__isnull=True), name="mawesi_estimate_one_per_issue"),
        ]

    def __str__(self):
        return f"{self.issue_id} · {self.original_minutes} / {self.remaining_minutes} min"


class StateLimit(ProjectBaseModel):
    """Límite de tareas (WIP) y definición de terminado de una columna del tablero (= estado del proyecto)."""

    state = models.ForeignKey("db.State", on_delete=models.CASCADE, related_name="mawesi_limits")
    wip_limit = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(999)])
    definition_of_done = models.TextField(blank=True, default="")

    class Meta:
        db_table = "mawesi_state_limits"
        constraints = [
            models.UniqueConstraint(fields=["state"], condition=models.Q(deleted_at__isnull=True), name="mawesi_limit_one_per_state"),
        ]


class CardRule(ProjectBaseModel):
    """Regla de color de la tarjeta (card styling de Azure DevOps). Se evalúa en el navegador con los datos que la
    tarjeta ya tiene; gana la primera que coincide. `conditions` = {"priorities": [...], "label_ids": [...],
    "state_ids": [...], "overdue": bool, "due_in_days": n, "unassigned": bool} (todas deben cumplirse)."""

    name = models.CharField(max_length=80)
    color = models.CharField(max_length=16)
    conditions = models.JSONField(default=dict)
    sort_order = models.PositiveSmallIntegerField(default=0)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "mawesi_card_rules"
        ordering = ("sort_order", "created_at")


class CyclePlan(ProjectBaseModel):
    """Días libres de todo el equipo en un ciclo (festivos propios, integración, etc.)."""

    cycle = models.ForeignKey("db.Cycle", on_delete=models.CASCADE, related_name="mawesi_plans")
    team_days_off = models.JSONField(default=list)  # ["2026-10-24", ...]

    class Meta:
        db_table = "mawesi_cycle_plans"
        constraints = [
            models.UniqueConstraint(fields=["cycle"], condition=models.Q(deleted_at__isnull=True), name="mawesi_plan_one_per_cycle"),
        ]


class CycleCapacity(ProjectBaseModel):
    """Horas por día que una persona le dedica al ciclo y sus días libres (Capacity de Azure DevOps)."""

    cycle = models.ForeignKey("db.Cycle", on_delete=models.CASCADE, related_name="mawesi_capacities")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mawesi_capacities")
    hours_per_day = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    days_off = models.JSONField(default=list)

    class Meta:
        db_table = "mawesi_cycle_capacities"
        constraints = [
            models.UniqueConstraint(fields=["cycle", "member"], condition=models.Q(deleted_at__isnull=True), name="mawesi_capacity_unique"),
        ]


class CodeProvider(models.TextChoices):
    GITHUB = "github", "GitHub"
    AZURE = "azure", "Azure Repos"


class CodeRepo(WorkspaceBaseModel):
    """Repositorio que MWSTASKS lee cada pocos minutos buscando ids de tareas (p. ej. TQ-123) en commits y PRs.
    Se LEE desde acá (no hay webhooks): MWSTASKS solo se ve por NetBird y GitHub/Azure no llegarían.
    Los tokens van por variables de entorno (MAWESI_GITHUB_TOKEN, MAWESI_AZURE_DEVOPS_TOKEN), nunca en la base."""

    provider = models.CharField(max_length=10, choices=CodeProvider.choices)
    # GitHub: owner/repo. Azure: organización/proyecto/repo.
    path = models.CharField(max_length=300)
    enabled = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    links_found = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "mawesi_code_repos"
        ordering = ("path",)
        constraints = [
            models.UniqueConstraint(fields=["workspace", "provider", "path"], condition=models.Q(deleted_at__isnull=True), name="mawesi_repo_unique"),
        ]

    def __str__(self):
        return f"{self.provider}:{self.path}"


class CodeLinkKind(models.TextChoices):
    COMMIT = "commit", "Commit"
    PULL_REQUEST = "pr", "Pull request"


class CodeLink(ProjectBaseModel):
    """Commit o PR que nombra una tarea. `state` del PR: open, merged, closed (abandoned en Azure)."""

    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="mawesi_code_links")
    repo = models.ForeignKey(CodeRepo, on_delete=models.CASCADE, related_name="links")
    kind = models.CharField(max_length=10, choices=CodeLinkKind.choices)
    external_id = models.CharField(max_length=80)  # sha o número del PR
    url = models.URLField(max_length=500)
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=120, blank=True, default="")
    state = models.CharField(max_length=16, blank=True, default="")
    branch = models.CharField(max_length=200, blank=True, default="")
    happened_at = models.DateTimeField()
    closed_issue = models.BooleanField(default=False)  # ya movió la tarea a terminado (una sola vez)

    class Meta:
        db_table = "mawesi_code_links"
        ordering = ("-happened_at",)
        constraints = [
            models.UniqueConstraint(fields=["issue", "repo", "kind", "external_id"], condition=models.Q(deleted_at__isnull=True), name="mawesi_code_link_unique"),
        ]


class DependencyPolicy(ProjectBaseModel):
    """Cómo se comportan las dependencias del proyecto (ver plane_mawesi/dependencies.py). Sin fila = todo prendido."""

    enforce = models.BooleanField(default=True)  # no dejar empezar ni terminar con bloqueos abiertos
    auto_unblock = models.BooleanField(default=True)  # de "Blocked" a la columna de por hacer al soltarse
    reschedule = models.BooleanField(default=True)  # correr las fechas de las dependientes si chocan

    class Meta:
        db_table = "mawesi_dependency_policies"
        constraints = [
            models.UniqueConstraint(fields=["project"], condition=models.Q(deleted_at__isnull=True), name="mawesi_dep_policy_one_per_project"),
        ]
