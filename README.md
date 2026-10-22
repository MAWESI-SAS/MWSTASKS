# MWSTASKS by MAWESI

Gestor de tareas de MAWESI basado en **[Plane](https://github.com/makeplane/plane) Community Edition** (AGPL-3.0), con:

- **Registro de horas** por tarea (detalle y vista rápida), historial y **reporte** con filtros y CSV.
- **Campos propios** por proyecto: texto, URL, número, fecha, sí/no, selección única y múltiple, persona.
  Los links se ven como en ClickUp: ícono del sitio + nombre (el servidor busca el favicon, sin servicios de terceros).
  Los nombres largos ocupan una línea y se cortan con "…"; el nombre completo y la descripción salen al pasar el mouse.
- **Tema y marca MAWESI**: colores, tipografías (Hanken Grotesk, Raleway), marco con gradiente, portadas.

No es un fork completo: se **monta sobre Plane oficial** para poder actualizarlo sin dolor.

## Cómo funciona

| Pieza | Cómo | Archivos de Plane tocados |
|---|---|---|
| Backend | Imagen oficial `makeplane/plane-backend:<versión>` + app Django `plane_mawesi` (se activa con `DJANGO_SETTINGS_MODULE`) | 0 |
| Web | Código oficial en el tag de `UPSTREAM_VERSION` + carpeta `ext/` + `vite.ext.config.ts` (envoltorios, reemplazos guardados) | 1 línea (`app/routes/extended.ts`) |
| Space, admin, live, proxy | Imágenes oficiales sin cambios | 0 |

Cada punto de contacto con Plane está en [`FORK.md`](FORK.md) y tiene un **guardia que hace fallar el build** si
Plane lo cambia en una actualización.

## Estructura

- `backend/`: app Django `plane_mawesi`, `Dockerfile` (sobre la imagen oficial), tests.
- `web/ext/`: overlay de la web (componentes, tema, marca, rutas); `web/vite.ext.config.ts`; `web/e2e/` (Playwright).
- `scripts/`: armado de la web sobre un checkout de Plane.
- `dev/`: entornos locales (ver `dev/README.md`).
- `tools/`: generadores (portadas).

## CI

- `.github/workflows/ci.yml` (push a `main` y PRs): pytest + `makemigrations --check` del backend sobre la imagen
  oficial; armado y build de la web sobre Plane@`UPSTREAM_VERSION` (con `tsc` y todos los guardias); E2E con
  Playwright contra el stack completo; en `main`, publica `ghcr.io/mawesi-sas/mwstasks-{backend,web}:<versión>-<sha>`.
- `.github/workflows/canary.yml` (lunes): arma contra el último RC de Plane y la rama `preview` para avisar antes.

## Verificar en local

```bash
# Backend
docker build -t plane-backend-mawesi:dev --build-arg UPSTREAM_VERSION=$(cat UPSTREAM_VERSION) backend
docker compose -f dev/compose.yaml up -d && curl http://127.0.0.1:8099/api/mawesi/ping/

# Web (dentro de un checkout de Plane en el tag de UPSTREAM_VERSION, con dependencias instaladas)
scripts/assemble-web.sh <plane-checkout> && scripts/build-web-client.sh <plane-checkout>
```

Detalles de las APIs más abajo.

## Licencia

AGPL-3.0-only, igual que Plane. Ver [`LICENSE`](LICENSE) y [`NOTICE.md`](NOTICE.md).
"Plane" es una marca de Plane Software, Inc.; este proyecto no está afiliado a Plane Software, Inc.
## API de horas (worklogs)

Web (cookie de sesión): prefijo `/api/mawesi/`. Pública (`X-Api-Key`): prefijo `/api/v1/mawesi/`.

| Método y ruta | Qué hace | Quién |
|---|---|---|
| `GET/POST workspaces/<slug>/projects/<pid>/issues/<iid>/worklogs/` | Lista / registra (`duration_minutes` 1–1440, `date` no futura, `description`, `member` opcional) | Admin y miembro. Solo un admin imputa a otra persona del proyecto |
| `PATCH/DELETE …/worklogs/<id>/` | Edita / borra | Quien registró o a quien se imputó (miembro), o un admin |
| `GET workspaces/<slug>/projects/<pid>/worklogs/totals/?issue_ids=a,b` | Minutos por tarea | Admin y miembro |
| `GET workspaces/<slug>/worklogs/report/?from=&to=&project_id=&member_id=` | Filas y total para facturar | Solo proyectos donde quien consulta es admin o miembro |

Tests: `docker build -t plane-backend-mawesi-test:dev -f backend/Dockerfile.test backend` y correrlo en la red de `dev/compose.yaml`.

## API de campos propios

| Método y ruta (prefijos como horas) | Qué hace | Quién |
|---|---|---|
| `GET/POST workspaces/<slug>/projects/<pid>/properties/` | Lista / crea (`name`, `type`, `options: [{name}]`) | Lee admin y miembro; crea admin |
| `PATCH/DELETE …/properties/<id>/` | Edita nombre/orden/opciones (`options` sincroniza: con `id` actualiza, sin `id` crea, las que faltan se borran) / borra (soft) | Admin. El tipo no se cambia |
| `GET/PATCH …/issues/<iid>/property-values/` | `{property_id: valor}` / `{"values": {property_id: valor\|null}}` todo-o-nada | Admin y miembro |
| `GET …/projects/<pid>/property-values/?issue_ids=a,b` | `{issue_id: {property_id: valor}}` | Admin y miembro |

Tipos y valor: `text`/`url` (string), `number`, `date` (`AAAA-MM-DD`), `checkbox` (bool), `select` (id de opción),
`multi_select` (lista de ids), `member` (id de usuario miembro del proyecto).

## Funciones de Azure DevOps

| Función | Dónde | Qué hace |
|---|---|---|
| Estimado y restante | Panel "Estimado" de la tarea + chip "hecho / estimado" en la tarjeta | Estimado y restante en horas; lo hecho son las horas registradas. Restante vacío = estimado − hecho |
| Límite por columna (WIP) y definición de terminado | Configuración del proyecto → Tablero | La columna se pone roja si tiene más tareas que el límite; ⓘ muestra la definición de terminado |
| Colores de tarjeta | Configuración del proyecto → Tablero | Reglas (vencida, vence en N días, prioridad, etiqueta, columna, sin responsable) → color. Gana la primera |
| Capacidad | Menú del proyecto → Capacidad | Por ciclo: horas por día y días libres de cada persona contra el restante de sus tareas |
| Flujo | Menú del proyecto → Flujo | Flujo acumulado, lead/cycle time, terminadas por semana y tareas en curso más viejas |
| Enlace con el código | Configuración del workspace → Repositorios + panel "Código" de la tarea | Commits y PRs de GitHub/Azure Repos que nombran `TQ-123`; `fixes TQ-123` cierra la tarea al aprobar el PR |

API pública del estimado (`X-Api-Key`, para los empleados AI): `GET/PUT /api/v1/mawesi/workspaces/<slug>/projects/<pid>/issues/<iid>/estimate/`
con `{"original_minutes", "remaining_minutes"}` (null borra) y `GET …/projects/<pid>/estimates/?issue_ids=a,b`.
El campo propio "Estimado (h)" que vino de ClickUp se copia al estimado con
`manage.py mawesi_import_estimates --workspace mawesi` (solo llena las tareas sin estimado; se puede repetir).

Repositorios: MWSTASKS los LEE cada 5 minutos (Celery), no recibe webhooks (solo se ve por NetBird). Tokens solo por
variables de entorno de api y worker: `MAWESI_GITHUB_TOKEN` (opcional: sin token solo repos públicos, 60 lecturas por hora) y
`MAWESI_AZURE_DEVOPS_TOKEN` (obligatorio para Azure Repos, permiso Code: Read).

## Dependencias

Relaciones de la tarea: "Bloqueada por / Bloqueando" (terminar para empezar), "Empieza después de / antes de" y
"Termina después de / antes de" (los dos últimos, que en Plane son pagos, se agregan al menú). Según Configuración del
proyecto → Tablero → Dependencias (todo prendido por defecto):

- **Frenar:** una tarea no pasa a "en curso" ni a "terminada" mientras lo que espera siga abierto (web y API; responde
  409 con el motivo). No frena a las integraciones de un admin del workspace con API key (la copia desde ClickUp).
- **Soltar al desbloquearse:** al resolverse lo último que esperaba, queda en el historial y, si estaba en "Blocked",
  pasa a la primera columna por hacer (con el aviso de Plane).
- **Correr fechas:** si una tarea se atrasa, sus dependientes se corren lo justo para no chocar (todas sus predecesoras
  cuentan; nunca se adelantan). La cadena sigue sola.
- No se pueden crear círculos. La tarjeta muestra "Bloqueada (n)" o "Fechas" si choca.

Las dependencias de ClickUp (waiting on / blocking) se copian con la migración y el `--prune` nocturno de la copia
incremental (`"relation_type": "blocked_by"` en `/api/v1/mawesi/workspaces/<slug>/relations/`).

## Empleados AI

Cada empleado AI de la plataforma de empleados MAWESI es un usuario de MWSTASKS: nombre, cargo, correo, avatar y su propio
token. Así cada tarea, cambio y comentario queda a su nombre y se puede medir. No pueden entrar a la web (sin contraseña).

```bash
docker compose exec -T mwstasks-api python manage.py mawesi_agents --workspace mawesi < agentes.json > tokens.jsonl
```

`agentes.json`: `[{"email", "name", "title", "projects": ["*"] | ["TQ", ...], "avatar_b64", "active"}]`. Idempotente.
Por stdout sale `{"email", "token"}` solo para tokens nuevos (Plane no los vuelve a mostrar); el resumen va a stderr.
`--rotate` cambia todos los tokens. `"active": false` da de baja: lo hecho queda a su nombre y el token deja de servir.
El comando no toca a una persona que ya exista con ese correo.
