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

| Clave | Envoltorio |
|---|---|
| `components/issues/peek-overview/properties` | `overrides/issues/peek-overview-properties.tsx`: propiedades de Plane + panel de horas |
| `components/issues/issue-detail/sidebar` | `overrides/issues/issue-detail-sidebar.tsx`: columna flex, Plane arriba con su scroll y el panel de horas abajo (Plane usa `h-full`; un hermano quedaba fuera de vista) |
| `components/issues/issue-detail/issue-activity/activity/activity-list` | `overrides/issues/activity-list.tsx`: pinta `field="worklog"`; el resto lo pinta Plane (que devuelve `null` para campos desconocidos) |
| `components/workspace/sidebar/helper` | `overrides/workspace/sidebar-helper.tsx`: ícono de reloj para el ítem `mawesi_worklogs`; re-exporta todo lo demás |
| `components/navigation/top-navigation-root` | `overrides/navigation/top-navigation-root.tsx`: envuelve la barra superior en `.mawesi-topbar` (`display: contents`, sin cambiar el layout) para pintarla en blanco sobre el gradiente |
| `components/workspace/sidebar/project-navigation` | `overrides/workspace/project-navigation.tsx`: pasa la prop `additionalNavigationItems` (existe en Plane, CE no la usa) con el ítem "Tabla" y dibuja debajo el árbol "Carpeta > Lista" (`folders/module-tree.tsx`), armado con los módulos `"Carpeta / Lista"`. Solo en el modo de menú "acordeón" (el de por defecto). El árbol es la única forma de ordenar listas: menús "⋯" para crear/renombrar/mover/borrar (`folders/tree-dialog.tsx`; mismos permisos que la API de módulos: crear/editar admin y miembro, borrar admin o creador) y el ítem "Módulos" de Plane se oculta con CSS (`folders/tree.css`, dentro de `[data-mawesi=project-nav]`) porque Plane lo arma en `baseNavigation` sin prop para quitarlo. Respeta el interruptor `module_view` del proyecto |
| `components/issues/issue-layouts/properties/all-properties` | `overrides/issues/all-properties.tsx`: chip de horas al final de las propiedades de la tarjeta (tablero y lista). El contenedor de Plane queda en `contents` para compartir el flex. Los totales se piden en lote por proyecto (`worklog/totals.ts`) |
| `helpers/cover-image.helper` | `overrides/helpers/cover-image.ts`: `handleCoverImageChange` completa `cover_image` con `window.location.origin` cuando sale relativa (con `API_BASE_URL=""` Plane manda `/api/assets/...` y `User.cover_image` es URLField → 400 al cambiar el cover del perfil). Quitar si Plane lo arregla |
| `hooks/oauth/extended` | `overrides/auth/oauth-extended.tsx`: punto de extensión de Plane para logins extra (en CE devuelve vacío). Suma "Continue with Microsoft" si `GET /api/mawesi/auth-providers/` dice que está configurado |

## Rutas y menú

- `ext/routes.ts` repite la cadena de layouts de Plane (`(all)/layout` → `[workspaceSlug]/layout` → `(projects)/layout`)
  para que `:workspaceSlug/mawesi/horas` quede dentro del workspace (Plane fusiona por archivo de layout).
  `scripts/assemble-web.sh` falla si Plane renombra alguno.
- `ext/routes.ts` también repite la cadena de ajustes (`(settings)/layout` → `settings/projects/layout` →
  `settings/projects/[projectId]/layout`) para `…/settings/projects/:projectId/mawesi-campos`.
- `ext/routes.ts` cuelga `…/projects/:projectId/mawesi-tabla` (vista Tabla) del layout de proyecto de Plane
  (`PROJECT_LAYOUT`), así `ProjectAuthWrapper` controla el acceso y carga estados y módulos.
- El aviso del cronómetro (`worklog/running-timer.tsx`) se monta en el envoltorio de `top-navigation-root`, fuera de
  `.mawesi-topbar` (que pinta todo en blanco).
- `ext/nav.ts` agrega "Campos" a `GROUPED_PROJECT_SETTINGS[WORK_STRUCTURE]`, `PROJECT_SETTINGS_FLAT_MAP` y
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

## Backend

Cero archivos de Plane editados. Se activa con `DJANGO_SETTINGS_MODULE=plane_mawesi.settings` en la imagen.
Internos de Plane que importamos (cubiertos por `tests/test_contrato_plane.py`): `plane.settings.production` / `.test`,
`plane.urls.urlpatterns`, `plane.app.views.base.BaseAPIView`, `plane.api.views.base.BaseAPIView` (+ `APIKeyAuthentication`),
`plane.app.permissions.ROLE`, `plane.db.models.project.ProjectBaseModel`, `Issue.issue_objects`, campos de `IssueActivity`.

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
