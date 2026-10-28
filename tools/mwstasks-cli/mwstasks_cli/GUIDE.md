# mws: guía para agentes

Con `mws` hacés en MWSTASKS **todo** lo que hace la web, con los permisos del dueño del token.
El CLI no tiene una lista fija de funciones: lee las operaciones del servidor. Si algo se puede hacer en la web, hay una operación para eso.

## Reglas
1. **Nunca digas "no hay una función para eso".** Buscala con `mws ops <palabras>`. Probá sinónimos y palabras en inglés (issue, cycle, module, label, state).
2. Antes de usar una operación nueva, mirá `mws op <id>`: parámetros, cuerpo de ejemplo y **quién** puede usarla.
3. Si de verdad no aparece, usá `mws call MÉTODO /ruta`: llama cualquier ruta de la API.
4. Si el servidor responde 403, el dueño del token no tiene ese permiso. No es una falla del CLI: avisá qué rol hace falta (lo dice `who` en `mws op`).
5. Antes de borrar o de cambiar muchas cosas, probá el pedido con `--dry-run`.

## Una sola versión de cada función
`mws ops` muestra la API de la web (`/api/…`) y la de MAWESI (`/api/mawesi/…`): ahí está todo lo que hace la web.
La API v1 (`/api/v1/…`) y los nombres viejos (`inbox` = `intake`) repiten lo mismo y quedan ocultos. Usala solo si alguien te lo pide
(`mws ops --v1`). `mws run` y `mws call` aceptan cualquiera.

## Configuración (variables de entorno)
- `MWSTASKS_TOKEN` (o `MWSTASKS_TOKEN_FILE`): token personal. Nunca lo muestres ni lo guardes en archivos del proyecto.
- `MWSTASKS_WORKSPACE`: slug del workspace (por ejemplo `mawesi`). Llena `{slug}` solo.
- `MWSTASKS_URL`: por defecto `https://tasks.mawesi.online`.

## Comandos
| Comando | Para qué |
|---|---|
| `mws whoami` | Dueño del token y sus workspaces. |
| `mws ops <palabras> [--tag Grupo]` | Buscar operaciones. `mws ops --tags` lista los grupos. |
| `mws op <id>` | Detalle de una operación. |
| `mws run <id> clave=valor … -d campo=valor` | Ejecutar una operación. También acepta `"MÉTODO /ruta"` como id. |
| `mws call MÉTODO /ruta clave=valor …` | Llamar cualquier ruta (la ruta puede llevar `{parámetros}`). |
| `mws attach TQ-123 archivo.pdf` | Adjuntar un archivo a una tarea (son 3 pasos, el CLI los hace). |
| `mws page-write <page_id> --project TQ --html @archivo.html` | Reemplazar el contenido de una Página. |

## Parámetros
- `clave=valor` llena los `{parámetros}` de la ruta. Lo que sobra va como `?clave=valor`.
- Atajos: `project=TQ` (identificador) llena `project_id`. `issue=TQ-123` (clave) llena `issue_id`, `project_id` y el `{pk}` de `…/issues/{pk}/`. `cycle=<uuid>` llena `cycle_id` (igual con cualquier `x=` para `{x_id}`).
- Cuerpo: `-d campo=valor` (se repite). El valor se lee como JSON si se puede: `-d priority=high -d assignee_ids='["<uuid>"]' -d target_date=null`. Para un cuerpo entero: `--body '{…}'`, `--body @archivo.json` o `--body -` (stdin).
- Archivos (multipart): `--file campo=ruta`.
- Listas largas: `--all` trae todas las páginas.

## Salida y errores
- Siempre JSON en stdout (`--compact` en una línea). Los errores van en JSON a stderr.
- Código de salida: 0 bien · 2 uso o falta un parámetro · 3 token inválido · 4 sin permiso, no existe o datos mal (`detail` dice por qué) · 5 servidor o red.
- El CLI espera solo si el servidor dice 429 (60 pedidos por minuto por token).
- 409 `dependency_blocked`: la tarea espera a otra que no terminó. Es una regla del proyecto, no un error.

## Ejemplos
```bash
mws ops crear tarea                       # → POST /api/workspaces/{slug}/projects/{project_id}/issues/
mws run "POST /api/workspaces/{slug}/projects/{project_id}/issues/" project=TQ -d name="Revisar informe" -d priority=high
mws run "PATCH /api/workspaces/{slug}/projects/{project_id}/issues/{pk}/" issue=TQ-123 -d state_id=<uuid del estado>
mws call GET /api/workspaces/{slug}/projects/{project_id}/states/ project=TQ
mws ops registrar horas                   # → mawesi_workspaces_projects_issues_worklogs_create
mws run mawesi_workspaces_projects_issues_worklogs_create issue=TQ-123 -d duration_minutes=90 -d date=2026-10-28
mws run "GET /api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/history/" issue=TQ-123 activity_type=issue-property
mws call GET /api/workspaces/{slug}/projects/{project_id}/issues/ project=TQ --all
mws attach TQ-123 informe.pdf
```

## Filtrar tareas
`GET /api/workspaces/{slug}/projects/{project_id}/issues/` (un proyecto) o `GET /api/workspaces/{slug}/issues/` (todo el
workspace) aceptan, separados por coma:
`state=<uuid>`, `state_group=backlog,unstarted,started`, `assignees=<uuid>`, `priority=urgent,high`, `labels=<uuid>`,
`module=<uuid de la lista>`, `cycle=<uuid>`, `parent=<uuid>`, `project=TQ` (en el del workspace),
`updated_at=2026-10-20;after`, `created_at=2026-10-01;after`, `target_date=2026-11-01;before`. Sumá `--all` para traer todo.

```bash
mws call GET /api/workspaces/{slug}/issues/ assignees=<uuid> state_group=unstarted,started --all
mws call GET /api/workspaces/{slug}/projects/{project_id}/issues/ project=TQ module=<uuid> "updated_at=2026-10-20;after" --all
```

## Si venís de ClickUp
| En ClickUp | En mws |
|---|---|
| Estado por nombre | `state_id` (de `GET …/states/`). Para cerrar: el estado del grupo `completed`. |
| Lista | Lista (módulo): `module=<uuid>` para filtrar; `POST …/modules/{module_id}/issues/` para poner una tarea. |
| Subtarea (`parent`) | Crear la tarea con `parent_id`. Ver: `GET …/issues/{issue_id}/sub-issues/`. |
| Tarea vinculada (link) | Relación `relates_to`: `POST …/issues/{issue_id}/issue-relation/`. Quitar: `…/remove-relation/`. |
| Campo personalizado por nombre | `GET /api/mawesi/…/properties/` (nombre → id) y `PATCH /api/mawesi/…/issues/{issue_id}/property-values/`. Selección: id de la opción. |
| Tipo de tarea (`custom_item_id`) | Tipos: `GET /api/mawesi/…/types/` y `PUT /api/mawesi/…/issues/{issue_id}/type/`. |
| Time entry (`team/{id}/time_entries`) | Horas: `POST /api/mawesi/…/issues/{issue_id}/worklogs/` (`member` = otra persona, solo admins). Listar: `GET /api/mawesi/workspaces/{slug}/worklogs/report/?from=&to=&member_id=&project_id=`. |
| `time_spent` | `GET /api/mawesi/…/worklogs/totals/?issue_ids=` (minutos). |
| Comentario (texto) | `comment_html` (HTML). |
| `markdown_content` | `description_html` (HTML). Convertí el markdown a HTML antes de mandarlo. |
| Adjunto | `mws attach`. También se pueden borrar (en ClickUp no). |
| Duplicar tarea | No hay una operación: leé la tarea, creá otra con los mismos datos y copiá los campos. |
| Miembros (`GET /team`) | `GET /api/workspaces/{slug}/members/` (trae el correo para buscar a la persona). |
| Webhooks | `…/webhooks/` del workspace: eventos de tareas, comentarios, listas, ciclos y proyectos, firmados con `X-Plane-Signature` (HMAC-SHA256). |

## Cosas de MWSTASKS que conviene saber
- Una **lista** es un módulo de Plane. Las **carpetas** son listas con nombre `"Carpeta / Lista"`.
- Relaciones: `relates_to`, `duplicate`, `blocked_by`, `blocking`, `start_before`, `start_after`, `finish_before`, `finish_after`.
- Prioridades: `urgent`, `high`, `medium`, `low`, `none`. Grupos de estado: `backlog`, `unstarted`, `started`, `completed`, `cancelled`.
- El historial de una tarea necesita `activity_type=issue-property` o `issue-comment` (sin él, Plane da 500).
- El token no puede: crear, ver o borrar tokens; desactivar la cuenta; borrar un workspace.
- Todo lo que hagas queda a nombre del dueño del token.
