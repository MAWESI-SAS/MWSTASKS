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
