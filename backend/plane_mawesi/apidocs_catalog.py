# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Documentación de las rutas MAWESI (`/api/mawesi/…` y su copia `/api/v1/mawesi/…`) para la API en /api/mawesi/docs/.

Nuestras vistas no usan serializers de DRF, así que la documentación automática solo vería la ruta. Acá va lo que
hace cada una, quién puede usarla, qué recibe y qué devuelve (ejemplos reales). La clave es (método, ruta sin el
prefijo de la familia), con los parámetros como los escribe drf-spectacular.
"""

P = "workspaces/{slug}/projects/{project_id}/"
I = P + "issues/{issue_id}/"
W = "workspaces/{slug}/"

ADMIN = "Solo admins del proyecto (o del workspace)."
MEMBERS = "Admins y miembros del proyecto. Los invitados (guest) no."
IDS = ("issue_ids", "Ids de tareas separados por coma (hasta 500).", True)
UUID = "3f9a1c2e-0000-4000-8000-000000000001"
UUID2 = "3f9a1c2e-0000-4000-8000-000000000002"


def op(summary, description, roles, *, body=None, resp=None, status=200, query=()):
    return {"summary": summary, "description": f"{description}\n\n**Quién:** {roles}", "body": body, "resp": resp,
            "status": status, "query": list(query)}


WORKLOG = {"id": UUID, "issue": UUID2, "project": UUID, "workspace": UUID, "member": UUID, "duration_minutes": 90,
           "date": "2026-10-27", "description": "Revisión con el cliente", "created_by": UUID,
           "created_at": "2026-10-27T15:00:00Z", "updated_at": "2026-10-27T15:00:00Z"}
PROPERTY = {"id": UUID, "project": UUID, "name": "Gerencia", "type": "select", "description": "", "sort_order": 1000,
            "is_active": True, "options": [{"id": UUID2, "name": "Finanzas", "color": "#3b82f6", "sort_order": 1000,
                                            "external_id": ""}], "external_source": "", "external_id": ""}
TYPE = {"id": UUID, "name": "Incidente", "description": "Algo que falla en producción", "color": "red",
        "is_default": False, "property_ids": [UUID2], "module_ids": [UUID]}
ESTIMATE = {"original_minutes": 480, "remaining_minutes": 300, "remaining_is_manual": False, "completed_minutes": 180}
TEMPLATE = {"id": UUID, "name": "Alta de cliente", "priority": "medium", "module_id": None, "assignee_ids": [UUID2],
            "checklist": ["Crear usuario", "Enviar accesos"],
            "subtasks": [{"name": "Configurar ambiente", "priority": "high", "checklist": []}], "add_parent_name": True}
RULE = {"id": UUID, "name": "Urgente al crear", "enabled": True, "trigger": "created", "trigger_value": "",
        "module_id": None, "actions": {"priority": "urgent", "assignee_ids": [UUID2]}, "runs": 4,
        "last_run_at": "2026-10-27T15:00:00Z"}
SLA_POLICY = {"id": UUID, "module_id": None, "hours": {"urgent": 4, "high": 8, "medium": 24, "low": 40, "none": 80},
              "timezone": "America/Bogota", "work_start": "08:00", "work_end": "18:00", "workdays": [0, 1, 2, 3, 4],
              "colombia_holidays": True}
TIMER = {"id": UUID, "started_at": "2026-10-27T15:00:00Z", "description": "", "issue_id": UUID2, "project_id": UUID,
         "issue_name": "Caída del portal", "issue_sequence": 653, "project_identifier": "ICE"}

CATALOG = {
    # Horas
    ("GET", I + "worklogs/"): op("Horas de una tarea", "Lista los registros de horas de la tarea.", MEMBERS,
                                 resp=[WORKLOG]),
    ("POST", I + "worklogs/"): op(
        "Registrar horas", "Crea un registro de horas. `duration_minutes` y `date` (AAAA-MM-DD) son obligatorios. `member` es opcional: sin él, las horas son de quien llama. "
        "Registrar horas de otra persona: solo admins. `duration_minutes` va de 1 a 1440. Sin fechas futuras.", MEMBERS,
        body={"duration_minutes": 90, "date": "2026-10-27", "description": "Revisión con el cliente"},
        resp=WORKLOG, status=201),
    ("PATCH", I + "worklogs/{pk}/"): op("Cambiar un registro de horas", "Cambia minutos, fecha, descripción o persona.",
                                        "Quien lo cargó (miembro) o un admin. Cambiar la persona: solo admins.",
                                        body={"duration_minutes": 120}, resp=WORKLOG),
    ("DELETE", I + "worklogs/{pk}/"): op("Borrar un registro de horas", "Lo borra y deja la fila en el historial.",
                                         "Quien lo cargó (miembro) o un admin.", status=204),
    ("GET", P + "worklogs/totals/"): op("Total de horas por tarea", "Minutos registrados de varias tareas.", MEMBERS,
                                        query=[IDS], resp={UUID2: 270}),
    ("GET", W + "worklogs/report/"): op(
        "Informe de horas", "Registros de horas del workspace (hasta 5.000) con totales. Solo de los proyectos donde "
        "quien llama es admin o miembro.", MEMBERS,
        query=[("from", "Desde (AAAA-MM-DD).", False), ("to", "Hasta (AAAA-MM-DD).", False),
               ("project_id", "Solo este proyecto.", False), ("member_id", "Solo esta persona.", False)],
        resp={"total_minutes": 90, "count": 1, "rows": [{"id": UUID, "date": "2026-10-27", "duration_minutes": 90,
                                                         "member_name": "ana", "project_identifier": "TQ",
                                                         "issue_sequence": 11383, "issue_name": "Informe mensual"}]}),
    ("GET", W + "worklogs/summary/"): op(
        "Horas por mes", "Minutos por mes y por proyecto, persona o lista. Se suma en la base (sirve para años).",
        MEMBERS, query=[("by", "project, member o module.", False), ("from", "Desde (AAAA-MM-DD).", False),
                        ("to", "Hasta (AAAA-MM-DD).", False)]),
    # Cronómetro
    ("GET", W + "timer/"): op("Mi cronómetro", "El cronómetro andando de quien llama, o `null`.", "Cualquier usuario.",
                              resp={"timer": TIMER}),
    ("DELETE", W + "timer/"): op("Descartar mi cronómetro", "Lo para sin guardar horas.", "Cualquier usuario.",
                                 status=204),
    ("POST", W + "timer/stop/"): op("Parar mi cronómetro", "Lo para y guarda el tiempo como horas (más de 24 h se "
                                    "parte en registros de 24 h).", "Cualquier usuario.",
                                    body={"description": "Soporte"}, resp={"worklogs": [WORKLOG]}),
    ("POST", I + "timer/start/"): op("Arrancar el cronómetro", "Arranca el cronómetro en la tarea. Si había otro "
                                     "andando, lo para y lo guarda (como ClickUp).", MEMBERS,
                                     body={"description": ""}, resp={"timer": TIMER, "stopped": []}, status=201),
    # Campos propios
    ("GET", P + "properties/"): op(
        "Campos del proyecto", "Lista los campos propios con sus opciones. Tipos: text, url, number, date, checkbox, "
        "select, multi_select, member. `?include_removed=1` (admins) suma los borrados que vinieron de ClickUp.",
        MEMBERS, resp=[PROPERTY]),
    ("POST", P + "properties/"): op("Crear un campo", "Crea un campo. Las opciones van solo en select y multi_select.",
                                    ADMIN, body={"name": "Gerencia", "type": "select",
                                                 "options": [{"name": "Finanzas", "color": "#3b82f6"}]},
                                    resp=PROPERTY, status=201),
    ("PATCH", P + "properties/{property_id}/"): op(
        "Cambiar un campo", "Cambia nombre, descripción, orden u opciones. El tipo no se puede cambiar. `options` "
        "reemplaza la lista: las que tienen `id` se editan, las nuevas se crean y las que faltan se borran.", ADMIN,
        body={"name": "Gerencia responsable"}, resp=PROPERTY),
    ("DELETE", P + "properties/{property_id}/"): op("Borrar un campo", "Lo oculta. Los valores quedan guardados.",
                                                    ADMIN, status=204),
    ("GET", I + "property-values/"): op("Valores de una tarea", "`{property_id: valor}`. Selección: id de la opción; "
                                        "persona: id del usuario; fecha: AAAA-MM-DD.", MEMBERS,
                                        resp={UUID: UUID2}),
    ("PATCH", I + "property-values/"): op("Cambiar valores de una tarea", "`null` borra el valor. Deja historial.",
                                          MEMBERS, body={"values": {UUID: UUID2, UUID2: None}}, resp={UUID: UUID2}),
    ("GET", P + "property-values/"): op("Valores de varias tareas", "`{issue_id: {property_id: valor}}`, con el mismo "
                                        "formato que los valores de una tarea (selección: id de la opción). Sin opciones borradas.",
                                        MEMBERS, query=[IDS]),
    # Tipos de tarea
    ("GET", P + "types/"): op("Tipos de tarea", "Cada tipo muestra solo sus campos. Una lista usa un solo tipo.",
                              MEMBERS, resp=[TYPE]),
    ("POST", P + "types/"): op(
        "Crear un tipo", "Colores: gray, red, orange, yellow, green, blue, purple, pink. `is_default`: tipo de las "
        "tareas sin lista con tipo. Elegir una lista acá la saca del tipo que la tenía.", ADMIN,
        body={k: v for k, v in TYPE.items() if k != "id"}, resp=TYPE, status=201),
    ("PATCH", P + "types/{type_id}/"): op("Cambiar un tipo", "Mismos campos que al crear; los que no mandás no cambian.",
                                          ADMIN, body={"property_ids": [UUID2]}, resp=TYPE),
    ("DELETE", P + "types/{type_id}/"): op("Borrar un tipo", "Sus tareas pasan al tipo de su lista. Los valores de "
                                           "los campos no se tocan.", ADMIN, status=204),
    ("GET", P + "issue-types/"): op("Tipo de varias tareas", "`source`: issue (elegido en la tarea), list (de su "
                                    "lista), project (el del proyecto) o null.", MEMBERS, query=[IDS],
                                    resp={UUID2: {"type_id": UUID, "source": "list"}}),
    ("GET", I + "type/"): op("Tipo de una tarea", "Tipo efectivo y los campos que muestra (`null` = todos).", MEMBERS,
                             resp={"type_id": UUID, "source": "list", "property_ids": [UUID2]}),
    ("PUT", I + "type/"): op("Elegir el tipo de una tarea", "`type_id: null` vuelve a automático (el de la lista).",
                             MEMBERS, body={"type_id": UUID}, resp={"type_id": UUID, "source": "issue",
                                                                     "property_ids": [UUID2]}),
    # Estimado
    ("GET", I + "estimate/"): op("Estimado de una tarea", "Estimado original y restante, en minutos. El restante se "
                                 "calcula solo (original − horas) salvo que alguien lo corrija.", MEMBERS,
                                 resp=ESTIMATE),
    ("PUT", I + "estimate/"): op("Cambiar el estimado", "`null` borra el valor. Mandar `remaining_minutes` lo deja fijo "
                                 "(manual) hasta que se borre.", MEMBERS, body={"original_minutes": 480},
                                 resp=ESTIMATE),
    ("GET", P + "estimates/"): op("Estimado de varias tareas", "Solo devuelve las que tienen estimado.", MEMBERS,
                                  query=[IDS], resp={UUID2: ESTIMATE}),
    # Comentarios
    ("GET", P + "last-comments/"): op("Último comentario de varias tareas", "El comentario más nuevo de cada tarea, "
                                      "en una sola consulta.", MEMBERS, query=[IDS],
                                      resp={UUID2: {"id": UUID, "comment_html": "<p>Listo</p>", "actor": UUID,
                                                    "created_at": "2026-10-27T15:00:00Z"}}),
    # Relaciones en lote
    ("POST", W + "relations/"): op(
        "Relaciones en lote por id externo", "Hasta 1.000 pares `[a, b]` de ids externos (p. ej. de ClickUp). "
        "`relation_type`: relates_to (por defecto) o blocked_by (`a` espera a `b`). Solo crea lo que falta.",
        "Solo admins del workspace (cruza proyectos).",
        body={"external_source": "clickup", "relation_type": "blocked_by", "pairs": [["86a1", "86a2"]]},
        resp={"creadas": 1, "ya_estaban": 0, "sin_tarea": 0, "convertidas": 0}),
    # Dependencias y tablero
    ("GET", P + "dependencies/"): op("Bloqueos de varias tareas", "Solo las bloqueadas o con fechas que chocan con "
                                     "las tareas de las que dependen.", MEMBERS, query=[IDS],
                                     resp={UUID2: {"blocked_by": [{"id": UUID, "key": "TQ-10", "name": "Aprobar diseño",
                                                                   "kind": "blocked_by", "state": "En curso"}],
                                                    "conflict": False}}),
    ("GET", P + "board/"): op("Configuración del tablero", "Límites WIP y definición de terminado por columna (estado), "
                              "colores de tarjeta y reglas de dependencias.", MEMBERS,
                              resp={"limits": {UUID: {"wip_limit": 5, "definition_of_done": "Probado en QA"}},
                                    "card_rules": [{"id": UUID2, "name": "Vencidas", "color": "#ef4444",
                                                    "conditions": {"overdue": True}, "enabled": True}],
                                    "dependencies": {"enforce": True, "auto_unblock": True, "reschedule": False}}),
    ("PUT", P + "board/"): op(
        "Guardar la configuración del tablero", "Reemplaza todo. Condiciones de una regla de color: priorities, "
        "label_ids, state_ids, overdue, due_in_days, unassigned.", ADMIN,
        body={"limits": {UUID: {"wip_limit": 5, "definition_of_done": ""}},
              "card_rules": [{"name": "Vencidas", "color": "#ef4444", "conditions": {"overdue": True}}],
              "dependencies": {"enforce": True, "auto_unblock": True, "reschedule": False}}),
    # SLA
    ("GET", P + "sla/"): op("Política de SLA", "Plazo por prioridad en horas hábiles (o `null`).", MEMBERS,
                            resp={"policy": SLA_POLICY}),
    ("PUT", P + "sla/"): op("Guardar la política de SLA", "Crea o cambia la política. `workdays`: 0 = lunes. "
                            "`module_id`: solo esa lista (o null = todo el proyecto).", ADMIN,
                            body={k: v for k, v in SLA_POLICY.items() if k != "id"}, resp={"policy": SLA_POLICY}),
    ("DELETE", P + "sla/"): op("Quitar la política de SLA", "", ADMIN, status=204),
    ("GET", P + "sla/issues/"): op("SLA de varias tareas", "Estado del plazo de cada tarea a la que aplica.", MEMBERS,
                                   query=[IDS]),
    ("GET", I + "sla/"): op("SLA y tiempo en cada estado", "SLA de la tarea (o `null`) y horas hábiles en cada estado.",
                            MEMBERS),
    # Plantillas, repetición, reglas
    ("GET", P + "templates/"): op("Plantillas de tarea", "", MEMBERS, resp=[TEMPLATE]),
    ("POST", P + "templates/"): op("Crear una plantilla", "Prioridades: urgent, high, medium, low, none.", MEMBERS,
                                   body={k: v for k, v in TEMPLATE.items() if k != "id"}, resp=TEMPLATE, status=201),
    ("PATCH", P + "templates/{template_id}/"): op("Cambiar una plantilla", "", "Admins o quien la creó.",
                                                  body={"name": "Alta de cliente v2"}, resp=TEMPLATE),
    ("DELETE", P + "templates/{template_id}/"): op("Borrar una plantilla", "", "Admins o quien la creó.", status=204),
    ("POST", P + "templates/{template_id}/apply/"): op(
        "Usar una plantilla", "`{name, module_id?}` crea la tarea con sus subtareas. `{issue_id}` agrega las subtareas a "
        "una tarea que ya existe.", MEMBERS, body={"name": "Alta de Acme"},
        resp={"issue_id": UUID, "sequence_id": 120, "subtasks": 1}, status=201),
    ("GET", I + "recurrence/"): op("Repetición de una tarea", "", MEMBERS,
                                   resp={"recurrence": {"id": UUID, "frequency": "weekly", "interval": 1,
                                                        "trigger": "complete", "occurrences": 3,
                                                        "next_start": "2026-11-03", "next_target": "2026-11-07"}}),
    ("PUT", I + "recurrence/"): op("Repetir una tarea", "`frequency`: daily, weekdays, weekly, monthly. `trigger`: "
                                   "complete (al completarla) o schedule (en la fecha de vencimiento). `interval`: 1 a "
                                   "30.", MEMBERS, body={"frequency": "weekly", "interval": 1, "trigger": "complete"}),
    ("DELETE", I + "recurrence/"): op("Dejar de repetir", "", MEMBERS, status=204),
    ("GET", P + "automations/"): op("Reglas automáticas", "Las reglas y, en el mismo pedido, los estados, etiquetas y "
                                    "plantillas para armarlas.", MEMBERS,
                                    resp={"rules": [RULE], "states": [], "labels": [], "templates": []}),
    ("POST", P + "automations/"): op(
        "Crear una regla", "`trigger`: created, added_to_list, state, priority (`trigger_value` = el estado o la "
        "prioridad). `actions`: assignee_ids, state_id, priority, label_ids, due_in_days, template_id.", ADMIN,
        body={k: RULE[k] for k in ("name", "trigger", "trigger_value", "module_id", "actions")}, resp=RULE,
        status=201),
    ("PATCH", P + "automations/{rule_id}/"): op("Cambiar o apagar una regla", "", ADMIN, body={"enabled": False},
                                                resp=RULE),
    ("DELETE", P + "automations/{rule_id}/"): op("Borrar una regla", "", ADMIN, status=204),
    # Capacidad y flujo
    ("GET", P + "capacity/cycles/"): op("Ciclos con fechas", "Del más nuevo al más viejo, y cuál es el actual.",
                                        MEMBERS, resp={"cycles": [{"id": UUID, "name": "Sprint 44",
                                                                   "start": "2026-10-26", "end": "2026-11-06"}],
                                                       "current_id": UUID}),
    ("GET", P + "cycles/{cycle_id}/capacity/"): op("Capacidad de un ciclo", "Horas disponibles contra trabajo restante, "
                                                   "por persona.", MEMBERS),
    ("PUT", P + "cycles/{cycle_id}/capacity/"): op(
        "Guardar capacidad", "`members`: horas por día y días libres. `team_days_off`: feriados del equipo.",
        "Cada miembro cambia su fila. Admins: todas las filas y los días del equipo.",
        body={"members": [{"member_id": UUID, "hours_per_day": 6, "days_off": ["2026-10-30"]}]}),
    ("GET", P + "flow/"): op("Analítica de flujo", "Flujo acumulado, lead time, cycle time, rendimiento y "
                             "envejecimiento.", MEMBERS,
                             query=[("days", "14, 30, 90 o 180.", False), ("module", "Solo esta lista.", False)]),
    # Otras
    ("GET", P + "table/"): op("Vista Tabla", "Tareas abiertas con horas y campos propios como columnas (hasta 3.000).",
                              MEMBERS, query=[("module", "Solo esta lista.", False),
                                              ("closed", "1 = incluir cerradas.", False)]),
    ("GET", W + "workload/"): op(
        "Carga de trabajo", "Por persona y por día (la vista Workload de ClickUp), de todos los proyectos donde quien llama es "
        "admin o miembro. El restante de cada tarea abierta se reparte en partes iguales entre los días hábiles de su inicio "
        "a su vencimiento (con una sola fecha, todo ese día) y entre sus responsables. Capacidad: horas por día de cada "
        "persona (8 si no se cambió) en días hábiles (lunes a viernes sin festivos de Colombia). `backlog`: sin fechas, "
        "vencidas y sin estimado. Sin `from`/`to`: dos semanas desde el lunes.", MEMBERS,
        query=[("from", "Desde (AAAA-MM-DD).", False), ("to", "Hasta (AAAA-MM-DD), hasta 93 días.", False),
               ("project", "Solo estos proyectos (ids separados por coma).", False), ("module", "Solo esta lista.", False)],
        resp={"from": "2026-10-26", "to": "2026-11-08", "days": [{"date": "2026-10-26", "workday": True}],
              "rows": [{"member_id": UUID, "display_name": "ana", "hours_per_day": 8.0,
                        "minutes": {"2026-10-26": 300.0}, "tasks": {"2026-10-26": 2},
                        "capacity": {"2026-10-26": 480.0}, "total_minutes": 300.0, "capacity_minutes": 4800.0,
                        "items": [{"key": "TQ-120", "name": "Informe", "share_minutes": 600.0,
                                   "days": {"2026-10-26": 300.0, "2026-10-27": 300.0}}],
                        "backlog": {"undated_count": 3, "overdue_count": 1, "unestimated": 2}}]}),
    ("PUT", W + "workload/capacity/"): op("Horas por día de una persona", "Para la Carga de trabajo: de 0 a 24.",
                                          "Solo admins del workspace.", body={"member_id": UUID, "hours_per_day": 6},
                                          resp={"member_id": UUID, "hours_per_day": 6.0}),
    ("GET", W + "wiki/"): op("Buscar en la Wiki", "Páginas de todos los proyectos de quien llama. Ignora tildes.",
                             MEMBERS, query=[("q", "Texto a buscar.", False)]),
    ("GET", W + "favicon/"): op("Ícono de un sitio", "Ícono (favicon) del sitio de un link.", "Cualquier usuario.",
                                query=[("host", "Dominio, p. ej. dev.azure.com.", True)]),
    ("GET", W + "code-repos/"): op("Repositorios de código", "", "Solo admins del workspace."),
    ("POST", W + "code-repos/"): op("Agregar un repositorio", "`provider`: github o azure. `path`: owner/repo o la URL.",
                                    "Solo admins del workspace.",
                                    body={"provider": "github", "path": "MAWESI-SAS/MWSTASKS"}, status=201),
    ("PATCH", W + "code-repos/{repo_id}/"): op("Prender o apagar un repositorio", "", "Solo admins del workspace.",
                                               body={"enabled": False}),
    ("DELETE", W + "code-repos/{repo_id}/"): op("Quitar un repositorio", "Los enlaces ya hechos quedan en las tareas.",
                                                "Solo admins del workspace.", status=204),
    ("POST", W + "code-repos/{repo_id}/sync/"): op("Leer un repositorio ahora", "", "Solo admins del workspace."),
    ("GET", I + "code-links/"): op("Commits y PRs de una tarea", "", MEMBERS),
    ("POST", P + "logo/"): op("Subir el logo del proyecto", "Multipart, campo `file`. PNG, JPG o WebP de hasta 512 KB.",
                              ADMIN),
    ("DELETE", P + "logo/"): op("Quitar el logo del proyecto", "Vuelve al emoji o ícono.", ADMIN),
}

# Las operaciones de Plane más usadas, con resumen en español y el cuerpo que esperan (leído del código de Plane).
# Rutas completas (sin el prefijo /api/ de la familia web). Solo cambia el texto: "Quién" sigue saliendo de Plane.
WP = "workspaces/{slug}/projects/{project_id}/"
WI = WP + "issues/{issue_id}/"


def plane(summary, description="", body=None):
    return {"summary": summary, "description": description, "body": body}


PLANE = {
    ("GET", "workspaces/{slug}/projects/"): plane("Proyectos del workspace"),
    ("GET", WP + "issues/"): plane("Listar tareas del proyecto", "Con páginas: `per_page` y `cursor` (`next_cursor`)."),
    ("POST", WP + "issues/"): plane(
        "Crear una tarea", "Prioridades: urgent, high, medium, low, none. Fechas AAAA-MM-DD.",
        {"name": "Revisar informe", "description_html": "<p>Detalle</p>", "priority": "high", "state_id": UUID,
         "assignee_ids": [UUID2], "label_ids": [], "parent_id": None, "start_date": "2026-10-28",
         "target_date": "2026-11-04"}),
    ("GET", WP + "issues/{pk}/"): plane("Ver una tarea"),
    ("PATCH", WP + "issues/{pk}/"): plane(
        "Cambiar una tarea", "Mandá solo lo que cambia: estado, responsables, prioridad, fechas, nombre, descripción, "
        "etiquetas, tarea padre. Si una dependencia lo frena: 409 `dependency_blocked`.",
        {"state_id": UUID, "assignee_ids": [UUID2], "priority": "urgent"}),
    ("DELETE", WP + "issues/{pk}/"): plane("Borrar una tarea"),
    ("POST", WP + "issues/{pk}/archive/"): plane("Archivar una tarea", "Solo tareas terminadas o canceladas."),
    ("DELETE", WP + "issues/{pk}/archive/"): plane("Sacar una tarea del archivo"),
    ("GET", WP + "issues/{issue_id}/history/"): plane(
        "Historial de una tarea", "`activity_type` es obligatorio: issue-property (cambios) o issue-comment "
        "(comentarios). Sin él, Plane responde 500."),
    ("GET", WI + "comments/"): plane("Comentarios de una tarea"),
    ("POST", WI + "comments/"): plane("Comentar una tarea", "", {"comment_html": "<p>Listo para revisar</p>"}),
    ("PATCH", WI + "comments/{pk}/"): plane("Cambiar un comentario", "", {"comment_html": "<p>Texto nuevo</p>"}),
    ("DELETE", WI + "comments/{pk}/"): plane("Borrar un comentario"),
    ("GET", WI + "sub-issues/"): plane("Subtareas de una tarea"),
    ("POST", WI + "sub-issues/"): plane("Agregar subtareas", "Convierte tareas existentes en subtareas de esta.",
                                        {"sub_issue_ids": [UUID2]}),
    ("GET", WI + "issue-relation/"): plane("Relaciones de una tarea"),
    ("POST", WI + "issue-relation/"): plane(
        "Relacionar tareas", "`relation_type`: relates_to, duplicate, blocked_by, blocking, start_before, start_after, "
        "finish_before, finish_after. Rechaza (400) una dependencia que cierra un círculo.",
        {"relation_type": "blocked_by", "issues": [UUID2]}),
    ("POST", WI + "remove-relation/"): plane("Quitar una relación", "", {"relation_type": "blocked_by",
                                                                         "related_issue": UUID2}),
    ("GET", WI + "issue-links/"): plane("Links de una tarea"),
    ("POST", WI + "issue-links/"): plane("Agregar un link a una tarea", "", {"url": "https://dev.azure.com/…",
                                                                            "title": "PR 120"}),
    ("DELETE", WI + "issue-links/{pk}/"): plane("Quitar un link"),
    ("POST", WI + "modules/"): plane("Poner una tarea en listas", "Una lista es un módulo de Plane. Las carpetas son "
                                     "listas con nombre «Carpeta / Lista».", {"modules": [UUID], "removed_modules": []}),
    ("POST", WI + "issue-subscribers/"): plane("Suscribir personas a una tarea", "", {"subscribers": [UUID2]}),
    ("POST", WI + "subscribe/"): plane("Suscribirme a una tarea"),
    ("DELETE", WI + "subscribe/"): plane("Desuscribirme de una tarea"),
    ("POST", WI + "reactions/"): plane("Reaccionar a una tarea", "", {"reaction": "👍"}),
    ("GET", WP + "states/"): plane("Estados del proyecto", "Grupos: backlog, unstarted, started, completed, cancelled."),
    ("POST", WP + "states/"): plane("Crear un estado", "", {"name": "En QA", "group": "started", "color": "#f59e0b"}),
    ("GET", WP + "issue-labels/"): plane("Etiquetas del proyecto"),
    ("POST", WP + "issue-labels/"): plane("Crear una etiqueta", "", {"name": "staging", "color": "#3b82f6"}),
    ("GET", WP + "members/"): plane("Miembros del proyecto", "`role`: 20 admin, 15 miembro, 5 invitado."),
    ("GET", WP + "cycles/"): plane("Ciclos del proyecto"),
    ("POST", WP + "cycles/"): plane("Crear un ciclo", "Las dos fechas o ninguna.",
                                    {"name": "Sprint 45", "start_date": "2026-11-09", "end_date": "2026-11-20"}),
    ("PATCH", WP + "cycles/{pk}/"): plane("Cambiar un ciclo", "", {"name": "Sprint 45 (corto)"}),
    ("GET", WP + "cycles/{cycle_id}/cycle-issues/"): plane("Tareas de un ciclo"),
    ("POST", WP + "cycles/{cycle_id}/cycle-issues/"): plane("Poner tareas en un ciclo", "", {"issues": [UUID2]}),
    ("DELETE", WP + "cycles/{cycle_id}/cycle-issues/{issue_id}/"): plane("Sacar una tarea de un ciclo"),
    ("POST", WP + "cycles/{cycle_id}/transfer-issues/"): plane("Pasar las tareas abiertas a otro ciclo", "",
                                                               {"new_cycle_id": UUID}),
    ("GET", WP + "modules/"): plane("Listas del proyecto", "Las carpetas son listas con nombre «Carpeta / Lista»."),
    ("POST", WP + "modules/"): plane("Crear una lista", "Para que quede dentro de una carpeta: «Carpeta / Lista».",
                                     {"name": "Soporte - TQ / Incidentes"}),
    ("PATCH", WP + "modules/{pk}/"): plane("Cambiar una lista", "Cambiar «Carpeta / …» la mueve de carpeta.",
                                           {"name": "Backlog - TQ / Mejoras 2027"}),
    ("GET", WP + "modules/{module_id}/issues/"): plane("Tareas de una lista"),
    ("POST", WP + "modules/{module_id}/issues/"): plane("Poner tareas en una lista", "", {"issues": [UUID2]}),
    ("DELETE", WP + "modules/{module_id}/issues/{issue_id}/"): plane("Sacar una tarea de una lista"),
    ("GET", WP + "pages/"): plane("Páginas del proyecto"),
    ("POST", WP + "pages/"): plane("Crear una página", "`access`: 0 pública, 1 privada. Para el contenido usá "
                                   "`mws page-write` o PATCH …/description/.",
                                   {"name": "Manual de soporte", "access": 0}),
    ("PATCH", WP + "pages/{page_id}/description/"): plane(
        "Cambiar el contenido de una página", "Mandá `description_html` y `description_binary: \"\"` para que el "
        "editor de la web lo rearme con el HTML nuevo.", {"description_html": "<h2>Título</h2><p>Texto</p>",
                                                          "description_binary": ""}),
    ("GET", WP + "views/"): plane("Vistas guardadas del proyecto"),
    ("GET", "workspaces/{slug}/search/"): plane("Buscar en el workspace", "`search`: texto. Busca tareas, proyectos, "
                                                "ciclos, listas y páginas."),
    ("GET", WP + "search-issues/"): plane("Buscar tareas del proyecto", "`search`: texto."),
    ("GET", "workspaces/{slug}/users/notifications/"): plane("Mis notificaciones"),
    ("POST", "workspaces/{slug}/users/notifications/{pk}/read/"): plane("Marcar una notificación como leída"),
    ("POST", "workspaces/{slug}/users/notifications/mark-all-read/"): plane("Marcar todas las notificaciones como leídas"),
    ("GET", "workspaces/{slug}/members/"): plane("Miembros del workspace"),
    ("GET", "users/me/"): plane("Mi perfil"),
}
