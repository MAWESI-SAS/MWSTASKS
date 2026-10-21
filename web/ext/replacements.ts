/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Módulos de Plane que envolvemos. Clave = ruta relativa a la raíz de "@/" (sin extensión).
 * Valor = envoltorio dentro de ext/. Cada clave es un punto de contacto con Plane: anotar en FORK.md.
 */
export const REPLACEMENTS: Record<string, string> = {
  "components/issues/peek-overview/properties": "overrides/issues/peek-overview-properties.tsx",
  "components/issues/issue-detail/sidebar": "overrides/issues/issue-detail-sidebar.tsx",
  "components/issues/issue-detail/issue-activity/activity/activity-list": "overrides/issues/activity-list.tsx",
  "components/workspace/sidebar/helper": "overrides/workspace/sidebar-helper.tsx",
  // Parecido a ClickUp: "Tabla" + árbol Carpeta > Lista en el menú, y horas en las tarjetas
  "components/workspace/sidebar/project-navigation": "overrides/workspace/project-navigation.tsx",
  "components/issues/issue-layouts/properties/all-properties": "overrides/issues/all-properties.tsx",
  // Dependencias: tipos "empieza antes/después" y "termina antes/después" en el menú Relaciones
  "components/relations": "overrides/relations/index.tsx",
  // Relaciones (p. ej. "related" de ClickUp) abiertas por defecto en el detalle y el peek
  "components/issues/issue-detail-widgets/relations/root": "overrides/issues/relations-collapsible.tsx",
  // Panel de una lista: sin "Invalid date" cuando la lista no tiene fechas (casi todas las migradas)
  "components/modules/analytics-sidebar/issue-progress": "overrides/modules/issue-progress.tsx",
  // Tablero: columnas vacías plegadas en franja vertical
  "components/issues/issue-layouts/kanban/default": "overrides/kanban/kanban-default.tsx",
  // Tablero: límite de tareas (WIP) y definición de terminado en el encabezado de cada columna
  "components/issues/issue-layouts/kanban/headers/group-by-card": "overrides/kanban/group-by-card.tsx",
  // Configuración > General: bloque "Logo con imagen" (el logo se dibuja con ext/projects/logo.tsx, ver vite.ext.config.ts)
  "components/project/form": "overrides/project/form.tsx",
  "components/common/breadcrumb-link": "overrides/common/breadcrumb-link.tsx",
  "components/navigation/top-navigation-root": "overrides/navigation/top-navigation-root.tsx",
  // Cover del perfil con API en el mismo origen (Plane manda URL relativa a un URLField)
  "helpers/cover-image.helper": "overrides/helpers/cover-image.ts",
  // Marca MWSTASKS by MAWESI
  "components/common/logo-spinner": "overrides/common/logo-spinner.tsx",
  "app/(all)/[workspaceSlug]/(projects)/star-us-link": "overrides/projects/star-us-link.tsx",
  "components/workspace/edition-badge": "overrides/workspace/edition-badge.tsx",
  "components/auth-screens/footer": "overrides/auth/footer.tsx",
  "components/core/page-title": "overrides/core/page-title.tsx",
  // Login con Microsoft (punto de extensión de Plane: hooks/oauth/extended)
  "hooks/oauth/extended": "overrides/auth/oauth-extended.tsx",
};
