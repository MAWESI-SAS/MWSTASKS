# Migración ClickUp → MWSTASKS

Copia un espacio de ClickUp a un proyecto de MWSTASKS.

- **ClickUp: solo lectura.** El cliente solo hace pedidos `GET`.
- **Se puede correr varias veces.** Todo lo creado lleva `external_source=clickup` y `external_id`. Lo que ya existe se salta.
- **Personas por email.** Si alguien no tiene cuenta en MWSTASKS, queda fuera de la tarea y aparece en los avisos.

## Qué se copia

| ClickUp | MWSTASKS |
|---|---|
| Espacio (carpetas elegidas) | Proyecto |
| Listas "Sprint …" | Ciclos (con las fechas de la lista) |
| Otras listas | Módulos |
| Estados | Estados (open→backlog, custom→started/unstarted, done→completed, cancelled→cancelled) |
| Tags | Etiquetas |
| Prioridad | Prioridad (normal→medium) |
| Subtareas | Work item padre |
| Descripción (markdown) + checklists | Descripción + link a la tarea original |
| Comentarios y respuestas | Comentarios ("Autor original: X — fecha") |
| Campos propios | Campos MWSTASKS (`/api/v1/mawesi/…/properties/`) |
| Tiempo estimado (`--estimate`) | Campo "Estimado (h)" |
| Horas registradas | Horas MWSTASKS (marca `[clickup:<id>]` en la nota) |

| Adjuntos de las tareas | Adjuntos (respeta el límite de subida de la instancia; los más grandes quedan como aviso) |
| Listas fuera de carpetas | Igual que las demás (`--folders "(sin carpeta)"` para elegirlas) |
| Campos de relación con otras tareas | Texto con los nombres de las tareas |

Horas: se piden para los miembros actuales **y** para todas las personas que aparecen en las tareas (ex empleados), desde 2020.

No se copian: dependencias, watchers, docs (van a Outline).

## Uso

```bash
# Tokens por variable de entorno. Nunca en archivos del repo.
export CLICKUP_TOKEN=...        # token personal de un admin de ClickUp
export MWSTASKS_TOKEN=...       # API token de un admin del workspace
uv run --with-requirements tools/migrate_clickup/requirements.txt \
  python -m tools.migrate_clickup.inventory 90144438515 --folders "Product,Sprints"   # solo mirar
uv run --with-requirements tools/migrate_clickup/requirements.txt \
  python -m tools.migrate_clickup.migrate --space 90144438515 --folders "Product,Sprints,Documentation" \
  --url http://localhost:8088 --workspace mawesi --project-name "Contractor Management" --identifier CM --estimate
```

Al final imprime un JSON con lo creado, los avisos y ejemplos de cada aviso.

## Personas (incluidos ex empleados)

La API de Plane no crea usuarios. `people_shell.py` corre dentro del contenedor api:

```bash
docker exec -i -e ACTION=add -e SLUG=mawesi -e PEOPLE="$(cat personas.json)" <api> python manage.py shell < tools/migrate_clickup/people_shell.py
# ... migración ...
docker exec -i -e ACTION=deactivate -e SLUG=mawesi -e PEOPLE="$(cat ex-empleados.json)" <api> python manage.py shell < tools/migrate_clickup/people_shell.py
```

Los ex empleados se crean **antes** de migrar, para que tareas, horas y comentarios queden a su nombre, y se **desactivan** al
terminar (no pueden entrar, ni con Microsoft). Para una corrida incremental posterior, volver a correr `add` antes y `deactivate` después.

## Prueba local

1. Levantar el stack completo (`dev/README.md`) y correr `dev/seed-qa.sh`.
2. `dev/seed-migration-pilot.sh mawesi personas.txt` crea el workspace, las personas y el token (última línea).
3. Correr la migración contra `http://localhost:8088`.

Plane limita los API tokens a 60 pedidos/minuto. En local `dev/full.env` lo sube con `API_KEY_RATE_LIMIT`.

## Pruebas

```bash
uv run --with-requirements tools/migrate_clickup/requirements.txt --with pytest python -m pytest -q tools/migrate_clickup/tests
```

## Copia incremental hasta el corte (`sync.py`)

Después de la migración completa, `sync.py` mantiene MWSTASKS al día con ClickUp. Es para el período en que la gente
sigue trabajando en ClickUp.

- **Una sola dirección:** ClickUp → MWSTASKS. Lo que se edite en MWSTASKS en una tarea que cambió en ClickUp se pisa.
- **Solo lo cambiado:** un único pedido trae las tareas cambiadas desde la corrida anterior (`date_updated_gt`), para todos los espacios.
- **Por cada tarea cambiada:**
  - si es nueva, la crea;
  - si ya existe, actualiza solo los campos que cambiaron (título, estado, prioridad, responsables, etiquetas, fechas, descripción y padre);
  - si cambió de lista, la saca del módulo o ciclo viejo y la pone en el nuevo;
  - agrega comentarios, adjuntos y valores de campos nuevos.
- **Horas:** revisa una ventana de `--time-days` días (por defecto 45). ClickUp no marca la tarea como cambiada al cargar horas.
- **`--prune`** (de noche): las tareas que ya no existen en ClickUp (borradas, archivadas o movidas fuera del alcance) reciben la etiqueta "Borrada en ClickUp". No se borra nada.
- **No hace:** editar ni borrar horas ya copiadas, y editar comentarios ya copiados.
- **Estado:** `state.json` guarda la hora de la última corrida, la lista y la descripción de cada tarea, y las horas ya copiadas. Si un proyecto falla, la próxima corrida vuelve a pedir desde el mismo punto.
- **Límite de la API:** pide a MWSTASKS cada 1,05 s, debajo de los 60/minute de `API_KEY_RATE_LIMIT`.

```json
// sync.json
{"workspace": "mawesi", "projects": [
  {"identifier": "CM", "space": "90144438515", "folders": ["Product", "Sprints", "Documentation"]},
  {"identifier": "TQ", "space": "49142129"}
]}
```

```bash
docker build -t mwstasks-clickup-sync:local tools/migrate_clickup
docker run --rm --env-file sync.env -v "$PWD/data:/data" mwstasks-clickup-sync:local \
  --config /data/sync.json --state /data/state.json --url https://tasks.mawesi.online --since "2026-10-14 00:00"
```

La primera corrida necesita `--since`, que marca desde cuándo buscar cambios. Las siguientes lo toman de `state.json`.
