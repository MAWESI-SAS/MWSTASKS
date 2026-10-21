# Plane MAWESI — registro de contactos con Plane

Este repo **no es un fork**: se monta sobre Plane CE oficial (versión en `UPSTREAM_VERSION`).
Diseño completo: ver la sección "Cómo funciona" del README.

Regla: todo punto donde nuestro código depende de un archivo concreto de Plane va en esta tabla.
Meta: la menor cantidad posible. Cada uno tiene un guardia que **falla el build** si Plane lo cambia.

## Archivos de Plane editados

| # | Archivo | Cambio | Guardia |
|---|---|---|---|
| E1 | `apps/web/app/routes/extended.ts` | `extendedRoutes` re-exporta `ext/routes` (1 línea). React Router carga `routes.ts` sin plugins de Vite, así que no hay otra forma. | `web/patches/extended-routes.sh`: el ancla debe aparecer exactamente 1 vez |

## Módulos de Plane envueltos (sin editarlos)

Tabla viva: `web/ext/replacements.ts`. Guardias en `web/vite.ext.config.ts`:
- Cada clave debe resolver a exactamente 1 archivo (en `core/` para v1.4.x o en la raíz de `apps/web` para la estructura de `preview`).
- Cada clave debe ser importada por la compilación del cliente.
- `tsc -p tsconfig.ext.json` comprueba que los props de los envoltorios sigan siendo compatibles.
- Si `ext/` (p. ej. `ext/plane.ts`) necesita un módulo envuelto, lo importa con `@upstream/…`, nunca con `@/…`: el resolvedor guarda la primera resolución de esa ruta y, si la hace `ext/` (que recibe el original), Plane tampoco recibe el envoltorio. Lo detecta la guardia "Plane ya no importa".

| Clave | Envoltorio |
|---|---|
| `components/issues/peek-overview/properties` | `overrides/issues/peek-overview-properties.tsx`: propiedades de Plane + panel de horas |
| `components/issues/issue-detail/sidebar` | `overrides/issues/issue-detail-sidebar.tsx`: columna flex, Plane arriba con su scroll y el panel de horas abajo (Plane usa `h-full`; un hermano quedaba fuera de vista) |
| `components/issues/issue-detail/issue-activity/activity/activity-list` | `overrides/issues/activity-list.tsx`: pinta `field="worklog"`; el resto lo pinta Plane (que devuelve `null` para campos desconocidos) |
| `components/workspace/sidebar/helper` | `overrides/workspace/sidebar-helper.tsx`: ícono de reloj para el ítem `mawesi_worklogs`; re-exporta todo lo demás |
| `components/navigation/top-navigation-root` | `overrides/navigation/top-navigation-root.tsx`: envuelve la barra superior en `.mawesi-topbar` (`display: contents`, sin cambiar el layout) para pintarla en blanco sobre el gradiente |
| `components/workspace/sidebar/project-navigation` | `overrides/workspace/project-navigation.tsx`: pasa la prop `additionalNavigationItems` (existe en Plane, CE no la usa) con el ítem "Tabla" y dibuja debajo el árbol "Carpeta > Lista" (`folders/module-tree.tsx`), armado con los módulos `"Carpeta / Lista"`. Solo en el modo de menú "acordeón" (el de por defecto). El árbol es la única forma de ordenar listas: menús "⋯" para crear/renombrar/mover/borrar (`folders/tree-dialog.tsx`; mismos permisos que la API de módulos: crear/editar admin y miembro, borrar admin o creador) y el ítem "Módulos" de Plane se oculta con CSS (`folders/tree.css`, dentro de `[data-mawesi=project-nav]`) porque Plane lo arma en `baseNavigation` sin prop para quitarlo. Respeta el interruptor `module_view` del proyecto |
| `components/issues/issue-layouts/properties/all-properties` | `overrides/issues/all-properties.tsx`: chip de horas al final de las propiedades de la tarjeta (tablero y lista). El contenedor de Plane queda en `contents` para compartir el flex. Los totales se piden en lote por proyecto (`worklog/totals.ts`). Pasa a Plane `displayProperties` apagando las propiedades sin valor (prioridad, fechas, responsables, etiquetas, estimado, lista, ciclo) y la lista/ciclo de la ruta actual, como Linear; el estado se apaga solo cuando la vista está agrupada por estado (lee `group_by` de `useIssues(useIssueStoreType()).issuesFilter`) |
| `components/issues/issue-layouts/kanban/default` | `overrides/kanban/kanban-default.tsx`: con `group_by=state` y sin subgrupos, las columnas vacías arrancan plegadas (franja de 44px de Plane). `collapsedGroups.group_by` pasa a significar "lo que la persona invirtió" (plegada = vacía XOR guardada), así el botón de plegar sigue andando en los dos sentidos |
| `components/project/form` | `overrides/project/form.tsx`: bloque "Logo con imagen" (`projects/logo-upload.tsx`, solo admins) arriba del formulario de Plane, que se vuelve a montar (`key` = url de la imagen) porque guarda una copia de `logo_props` y la manda entera en "Update project" |
| `components/issues/issue-layouts/kanban/headers/group-by-card` | `overrides/kanban/group-by-card.tsx`: con `group_by=state` y sin subgrupos, suma al encabezado de la columna el límite WIP (`conteo/límite`, rojo si se pasa; el conteo es el de Plane con los filtros actuales) y el ícono ⓘ con la definición de terminado (`board/use-board.ts`, un pedido por proyecto) |
| `components/modules/analytics-sidebar/issue-progress` | `overrides/modules/issue-progress.tsx`: no dibuja "Progress" en el panel de una lista sin fechas (Plane mostraba "Invalid date. Please enter valid date.") |
| `components/issues/issue-detail-widgets/relations/root` | `overrides/issues/relations-collapsible.tsx`: la sección "Relaciones" sale abierta al entrar a cada tarea (detalle y peek); Plane la arranca cerrada (`openWidgets` por defecto no incluye `relations`) y las relaciones migradas de ClickUp quedaban escondidas. Si se cierra, queda cerrada hasta abrir otra tarea. E2E `web/e2e/relations.py` |
| `components/common/breadcrumb-link` | `overrides/common/breadcrumb-link.tsx`: no pinta la miga "Modules" (href `/projects/<id>/modules/`); las listas se ordenan solo desde el árbol. El resto de migas las pinta Plane |
| `helpers/cover-image.helper` | `overrides/helpers/cover-image.ts`: `handleCoverImageChange` completa `cover_image` con `window.location.origin` cuando sale relativa (con `API_BASE_URL=""` Plane manda `/api/assets/...` y `User.cover_image` es URLField → 400 al cambiar el cover del perfil). Quitar si Plane lo arregla |
| `hooks/oauth/extended` | `overrides/auth/oauth-extended.tsx`: punto de extensión de Plane para logins extra (en CE devuelve vacío). Suma "Continue with Microsoft" si `GET /api/mawesi/auth-providers/` dice que está configurado |

## Rutas y menú

- `ext/routes.ts` repite la cadena de layouts de Plane (`(all)/layout` → `[workspaceSlug]/layout` → `(projects)/layout`)
  para que `:workspaceSlug/mawesi/horas` quede dentro del workspace (Plane fusiona por archivo de layout).
  `scripts/assemble-web.sh` falla si Plane renombra alguno.
- Horas tiene 2 pestañas (`?vista=mes` en la URL): "Detalle" (`worklogs/report/`, hasta 5.000 registros) y "Por mes"
  (`worklogs/summary/?by=project|member|module`, sumado en la base con `TruncMonth`; "Lista" toma la primera lista
  de la tarea para no contar 2 veces). Cada celda abre el Detalle filtrado. Cliente = proyecto.
- `ext/routes.ts` también repite la cadena de ajustes (`(settings)/layout` → `settings/projects/layout` →
  `settings/projects/[projectId]/layout`) para `…/settings/projects/:projectId/mawesi-campos`.
- `ext/routes.ts` cuelga `…/projects/:projectId/mawesi-tabla` (vista Tabla) del layout de proyecto de Plane
  (`PROJECT_LAYOUT`), así `ProjectAuthWrapper` controla el acceso y carga estados y módulos.
- El aviso del cronómetro (`worklog/running-timer.tsx`) se monta en el envoltorio de `top-navigation-root`, fuera de
  `.mawesi-topbar` (que pinta todo en blanco).
- Wiki: `:workspaceSlug/mawesi/wiki` (misma cadena de layouts que Horas) + ítem "Wiki" en
  `WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS` (`registerWikiNav`; si no está fijado, Plane lo pone en "More").
  API `GET /api/mawesi/workspaces/<slug>/wiki/?q=` (`views/wiki.py`): Páginas de los proyectos donde la persona es
  admin o miembro, sin archivadas, privadas solo de su dueño; busca sin tildes con `translate()` de Postgres.
- SLA (`plane_mawesi/sla.py`, `views/sla.py`, tabla `mawesi_sla_policies`): una política por proyecto (plazo por
  prioridad en horas hábiles, horario, días, festivos de Colombia, lista opcional). Se configura en
  `…/settings/projects/:projectId/mawesi-sla` (ítem "SLA" junto a "Campos"). Chip en la tarjeta (envoltorio de
  `all-properties`, pedidos juntados con `lib/batcher.ts`) y panel "Tiempo y SLA" en el peek y el detalle. El tiempo
  por estado sale de `IssueActivity(field="state")`; los cerrados usan `Issue.completed_at`.
- Plantillas de tarea (`plane_mawesi/templates.py`, `views/templates.py`, tabla `mawesi_task_templates`): prioridad,
  lista, responsables, checklist y subtareas. Las tareas se crean con `IssueCreateSerializer` de Plane + su
  `issue_activity` (al hacer commit), igual que crearlas a mano. Las subtareas se crean al revés porque Plane las lista
  de la más nueva a la más vieja. Se configuran en `…/settings/projects/:projectId/mawesi-plantillas`; se usan desde el
  menú "⋯" de una lista del árbol (tarea nueva) y con el botón del panel del detalle (subtareas para una tarea existente).
- Tareas que se repiten (`plane_mawesi/recurrence.py`, `views/recurrence.py`, `tasks.py`, tabla `mawesi_recurrences`):
  la regla apunta a la ocurrencia vigente; `run_recurrences` (Celery, cada minuto, horario cargado en
  `django_celery_beat` por la migración `0006`) crea la siguiente al completarla o al llegar su vencimiento, con
  `create_issue` de plantillas y `crum.impersonate` del autor de la regla. Panel "Repetir" en el peek y el detalle.
- Reglas automáticas (`plane_mawesi/automations.py`, `views/automations.py`, tabla `mawesi_automations`): "Cuando se crea /
  entra a una lista / cambia estado / cambia prioridad → asignar, estado, prioridad, etiquetas, vencimiento, subtareas de
  plantilla". El disparo es el historial de Plane: su tarea `issue_activity` guarda con `bulk_create` (sin post_save),
  así que se leen sus filas en `task_postrun` (señales de Celery conectadas en `apps.py`); las filas creadas de a una
  llegan por `post_save`. Las acciones escriben su historial con `comment="mawesi-automation"`, que no dispara reglas.
- Funciones de Azure DevOps (ver README):
  - Estimado (`estimates.py`, tabla `mawesi_issue_estimates`): panel en el peek y el detalle; el chip de horas de la
    tarjeta pasa a "hecho / estimado". Historial con `field="estimate_hours"` (lo pinta `estimates/estimate-activity.tsx`).
  - Tablero (`board.py`, tablas `mawesi_state_limits` y `mawesi_card_rules`): `…/settings/projects/:projectId/mawesi-tablero`.
    Los colores de tarjeta NO editan Plane: `board/card-style.tsx` deja una marca oculta dentro de las propiedades (envoltorio
    de `all-properties`) y `board/card-style.css` pinta con `:has()` la tarjeta (`.group/kanban-block > a`) o la fila
    (`.group/list-block`). Si Plane cambia esas clases, los colores dejan de verse (lo cubre `web/e2e/board.py`).
  - Capacidad (`capacity.py`, tablas `mawesi_cycle_capacities` y `mawesi_cycle_plans`) y Flujo (`flow.py`, sin tablas: lee
    `IssueActivity(field="state")`): rutas `…/projects/:projectId/mawesi-capacidad` y `…/mawesi-flujo` en `PROJECT_LAYOUT`,
    ítems "Capacidad" y "Flujo" en el menú del proyecto (mismo `additionalNavigationItems` que "Tabla").
  - Repositorios (`code.py`, tablas `mawesi_code_repos` y `mawesi_code_links`): `:workspaceSlug/settings/mawesi-repos` cuelga
    del layout de Configuración del workspace (`WORKSPACE_SETTINGS_LAYOUT` en `ext/routes.ts`). `registerWorkspaceSettings`
    agrega el ítem a `GROUPED_WORKSPACE_SETTINGS[DEVELOPER]`, su ícono a `WORKSPACE_SETTINGS_ICONS` y la URL a
    `WORKSPACE_SETTINGS_ACCESS` (el layout de Plane autoriza por URL: sin esa entrada muestra "no autorizado").
    `sync_code_repos` corre cada 5 minutos (migración `0008`). Cierra tareas con `issue.save()` + su fila de historial
    (`comment="mawesi-code"`), como las reglas.
- `ext/nav.ts` agrega "Campos", "SLA", "Plantillas", "Reglas" y "Tablero" a `GROUPED_PROJECT_SETTINGS[WORK_STRUCTURE]`, `PROJECT_SETTINGS_FLAT_MAP` y
  `PROJECT_SETTINGS_ICONS` (objetos exportados de Plane, mutables).
- `ext/nav.ts` agrega "Horas" a `WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS` (arreglo exportado de Plane). Aparece
  en "More" (como Vistas/Análisis) y cada usuario puede fijarlo. El label no existe en el i18n de Plane: se muestra tal cual.

Imports de Plane desde ext/: **solo** en `web/ext/plane.ts` (adaptador único).

Trampa conocida (modales): el peek de Plane se cierra con cualquier clic fuera de él
(`hooks/use-peek-overview-outside-click.tsx`) y los modales viven en un portal. Plane lo evita con banderas
fijas de su store. En ext/ usar SIEMPRE `ui/modal.tsx` (MawesiModal) y `ui/confirm.tsx`, que llevan
`data-prevent-outside-click` en toda la capa; nunca `ModalCore`/`AlertModalCore` de Plane.

Trampa conocida (API): `APIService.get(url, params)` de Plane esparce el 2º argumento en la config de axios.
Los query params van como `this.get(url, { params: {...} })`. Pasarlos directo los pierde sin error.

Trampa conocida: los métodos de los stores MobX de Plane (`action`, no `action.bound`) pierden `this` al
desestructurarlos. Usar las funciones flecha del store raíz (p. ej. `useIssueDetail().fetchActivities`).

## Inyecciones

| Dónde | Qué |
|---|---|
| `apps/web/app/entry.client.tsx` (en memoria, vía plugin `transform`) | `import "ext/register"` |
| `@plane/propel/emoji-icon-picker` (módulo virtual en `vite.ext.config.ts`, como los logos de marca) | Reexporta todo y pisa `Logo` con `ext/projects/logo.tsx`: si `logo_props.image.url` existe dibuja la imagen, si no el emoji/ícono de Plane. Desde `ext/` el import llega al original (`PlaneLogo` en `ext/plane.ts`). El build falla si nadie importa el paquete |
| `kanban/default.tsx`, `kanban/block.tsx`, `kanban/swimlanes.tsx`, `modules/(detail)/[moduleId]/page.tsx` y `modules/(detail)/header.tsx` (en memoria, `ext/text-patches.ts`, sección "Diseño") | Columnas del tablero de 280px (vacías 200px) en vez de 350px; título de la tarjeta en hasta 2 líneas (`kanban/block.tsx`); panel de la lista cerrado por defecto (`module_sidebar_collapsed` = `"true"`). El build falla si Plane cambia el texto |

## Backend

Cero archivos de Plane editados. Se activa con `DJANGO_SETTINGS_MODULE=plane_mawesi.settings` en la imagen.
Internos de Plane que importamos (cubiertos por `tests/test_contrato_plane.py`): `plane.settings.production` / `.test`,
`plane.urls.urlpatterns`, `plane.app.views.base.BaseAPIView`, `plane.api.views.base.BaseAPIView` (+ `APIKeyAuthentication`),
`plane.app.permissions.ROLE`, `plane.db.models.project.ProjectBaseModel`, `plane.db.models.workspace.WorkspaceBaseModel`,
`Issue.issue_objects`, campos de `IssueActivity`, `Cycle`/`CycleIssue`/`IssueAssignee`/`State` y que `Issue.save()` ponga
`completed_at`.
Logo del proyecto (`views/project_logo.py`): `S3Storage().upload_file` (sin `request`: con MinIO apuntaría al host del navegador), `FileAsset` tipo `PROJECT_COVER` creado sin el flujo de subida de Plane (ese flujo lo pondría de portada) y servido por `/api/assets/v2/static/<id>/`; la imagen va en `Project.logo_props.image`.
Empleados AI (`agents.py`, comando `mawesi_agents`): crean `User` normales (no `is_bot`: Plane filtra `member__is_bot=False` en responsables, búsqueda y reportes), `WorkspaceMember`/`ProjectMember` + `ProjectUserProperty` como `ProjectMemberListCreateAPIEndpoint`, `APIToken` (`label`, `user_type=0`) que usa `APIKeyAuthentication`, y el avatar como `FileAsset` `USER_AVATAR` sin workspace + `User.avatar_asset`. Contrato: `test_agents.py::test_el_token_actua_como_el_empleado`.

Login con Microsoft (`plane_mawesi/auth/`): `MicrosoftOAuthProvider` hereda `plane.authentication.adapter.oauth.OauthAdapter`
(mismo contrato que `GoogleOAuthProvider`) y las vistas copian el flujo de `GoogleOauthInitiateEndpoint`/`GoogleCallbackEndpoint`
(`base_host`, `user_login`, `get_redirection_path`, `post_user_auth_workflow`, `get_safe_redirect_url`). Rutas propias
`/auth/microsoft/` y `/auth/microsoft/callback/`, antes de las de Plane. Config solo por env (`MICROSOFT_*`), sin UI en god-mode.
`Account.provider="microsoft"` no está en `PROVIDER_CHOICES` de Plane (Django no lo valida en DB). Contrato: `test_molde_oauth_para_microsoft`.

Historial: escribimos filas `IssueActivity(field="worklog")` directamente. Los guests de un proyecto las verían en el
historial core (hoy no hay guests).

## Imágenes

| Servicio | Imagen |
|---|---|
| api, worker, beat-worker, migrator | `backend/Dockerfile`: `FROM makeplane/plane-backend:<UPSTREAM_VERSION>` + `plane_mawesi` |
| web | `web/Dockerfile`: `FROM makeplane/plane-frontend:<UPSTREAM_VERSION>` (nginx oficial) + cliente compilado con el overlay |
| space, admin, live, proxy | oficiales, sin cambios |

## Tema MAWESI (look and feel)

- `ext/theme/gen_theme.py` (lo corre `assemble-web.sh`) genera `mawesi-theme.generated.css` desde los tokens de la
  versión de Plane que se arma: escala `--brand-*` con la paleta MAWESI (azul marino #213062 como primario en claro,
  violeta en oscuro, lavanda en tonos suaves, igual que MWSign) y `--neutral-*` de Plane con tono 290° y un poco de
  croma (valores de MWSign). Falla si Plane deja de definir `--brand-*`, `--neutral-*`, `--font-body` o `--font-heading`.
- Reglas sin `@layer`: ganan a los tokens de Plane (que están en `@layer base/theme`) sin importar el orden de carga.
- Tipografías: Hanken Grotesk (texto, vía `--font-body`) y Raleway (títulos propios, clase `font-heading`), servidas
  desde `ext/theme/fonts/` (SIL OFL 1.1, licencias incluidas). Plane no usa `font-heading`: sus títulos quedan en
  Hanken Grotesk.
- Probado también contra `preview` (tokens en `@makeplane/propel/dist/styles/variables.css`, mismos nombres y selector).
- Marco MAWESI (`ext/theme/shell.css`): `--bg-canvas` (gris de Plane, pintado por 4 contenedores) pasa a transparente y
  el `body` lleva el gradiente azul marino → violeta con brillo lavanda (estilo MWSign; versión profunda en oscuro).
  La barra superior redefine `--txt-*`, `--bg-layer-*`, `--bg-surface-*` y `--border-*` dentro de `.mawesi-topbar`
  (blanco y vidrio). **Trampa:** Plane dibuja los menús de la barra (workspace, usuario) DENTRO de ella; se restauran
  con `--mawesi-orig-*` (copias calculadas en `:root`) en `[role=menu|listbox|dialog]`.
- Portadas de proyecto: `assemble-web.sh` reemplaza las fotos de stock de Plane (`app/assets/cover-images/image_N.jpg`,
  29 en v1.4.2 y preview) por portadas MAWESI generadas con `tools/gen_covers.py` (deterministas, paleta MWSign). Falla
  si Plane cambia la cantidad. **Trampa:** Plane guarda en la base la URL con hash (`/assets/image_3-<hash>.jpg`), que
  cambia al reemplazar o actualizar. `web/Dockerfile` incluye `ext/nginx/covers.conf` en el nginx oficial (inserta
  `include` tras `listen 3000;`, con guardia y `nginx -t`) y sirve cualquier `image_N-<hash>.jpg` con la portada N
  actual. Verificado: una URL vieja sigue respondiendo con la portada MAWESI.
- El proyecto de demostración que Plane crea con cada workspace nuevo usa una foto de Unsplash (viene del backend).
- Logo y nombre "Plane": sin cambios (decisión de marca pendiente).

## Límites conocidos (v1)

- Campos propios: no se cargan en el modal de **crear** tarea (se cargan después, en detalle o peek). Los stubs del
  provider del modal existen (`issue-modal/provider`) para hacerlo más adelante.
- Campos propios no salen como columnas ni filtros en las listas de Plane (requiere tocar core). Lectura en lote
  disponible por API (`…/property-values/?issue_ids=`).

## Hallazgos conocidos de Plane (no son nuestros)

- React error #418 (hidratación): 38 en la home, **idéntico** con la web oficial `v1.4.2`.
- El worker manda métricas a `telemetry.plane.so` por defecto.
- `GET .../issues/<id>/history/` **sin** `activity_type` da 500 siempre (`app/views/issue/activity.py:81-84` ordena instancias con `instance["created_at"]`). La web siempre manda `activity_type`, así que no afecta a usuarios. Nuestras filas `field="worklog"` salen con `?activity_type=issue-property`.

- Cambiar el cover del perfil da `PATCH /api/users/me/` 400 si la web se compila sin `VITE_API_BASE_URL` (mismo origen): `getFileURL` devuelve ruta relativa y `User.cover_image` es URLField. Lo tapa `overrides/helpers/cover-image.ts`.

## Canary contra `preview` (próxima v1.5) — 2026-10-14

Commit upstream probado: `bab49bb978` (2026-10-08). Resultado: el overlay base, el parche de rutas, las cadenas de
layouts y las 14 rutas internas `@/…` que usa `ext/plane.ts` **siguen existiendo**. Falla **solo** `ext/plane.ts`
porque Plane reemplaza su librería de UI. Al adoptar la versión que traiga esto, ajustar estas líneas del adaptador
(y revisar props con `tsc -p tsconfig.ext.json`):

| Hoy (v1.4.x) | En `preview` |
|---|---|
| `Button` de `@plane/propel/button` | `@makeplane/propel/components/button` |
| `TOAST_TYPE`, `setToast` de `@plane/propel/toast` | `@plane/blocks/toast` |
| `Input` de `@plane/ui` | `@makeplane/propel/components/input` |
| `TextArea` de `@plane/ui` | `@makeplane/propel/components/text-area` |
| `Breadcrumbs` de `@plane/ui` | `@plane/blocks/breadcrumb` |
| `Header` de `@plane/ui` | `@plane/blocks/layout` |
| `PlaneLogo`/`PlaneLockup`/`PlaneWordmark` de `@plane/propel/icons` | `@plane/blocks/icons` (**ya soportado**: el plugin intercepta ambos) |

Estado del canary contra `preview` (2026-10-14, `4605f0078f`): reemplazos de texto, logos, rutas, tema y portadas OK;
falla solo `ext/plane.ts` (`@plane/propel/button`), que es la tabla de arriba.

Ya resuelto para no depender de la librería: `ToggleSwitch` → `ext/ui/toggle.tsx`; `ModalCore`/`AlertModalCore`/
`EModal*` → `ext/ui/modal.tsx` y `ext/ui/confirm.tsx`.

## Reglas de actualización

1. Cambiar `UPSTREAM_VERSION`. Nada más en el mismo PR, salvo los ajustes que pidan los guardias.
2. Merge **sin squash**. Escribir en el PR qué se ajustó y por qué.
3. Nunca crear migraciones en la app `db` de Plane: solo en `mawesi`.
