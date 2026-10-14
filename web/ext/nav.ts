/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Entrada "Horas" en la sección Workspace del menú lateral. Se agrega al arreglo exportado de Plane
 * (WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS) al cargar la app, sin editar Plane.
 * labelTranslationKey no existe en el i18n de Plane: i18next muestra la clave tal cual ("Horas").
 */
import { ListChecks } from "lucide-react";
import {
  EUserProjectRoles,
  EUserWorkspaceRoles,
  GROUPED_PROJECT_SETTINGS,
  PROJECT_SETTINGS_CATEGORY,
  PROJECT_SETTINGS_FLAT_MAP,
  PROJECT_SETTINGS_ICONS,
  WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS,
} from "./plane";
import type { TProjectSettingsItem } from "./plane";

export const MAWESI_NAV_KEY = "mawesi_worklogs";

export const registerNav = () => {
  if (WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS.some((i) => i.key === MAWESI_NAV_KEY)) return;
  WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS.push({
    key: MAWESI_NAV_KEY,
    labelTranslationKey: "Horas",
    href: "/mawesi/horas/",
    access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER],
    highlight: (pathname: string, url: string) => pathname.includes(url),
  });
};

export const MAWESI_FIELDS_KEY = "mawesi_fields";

/** "Campos" en Configuración del proyecto → Estructura de trabajo (objetos exportados de Plane, mutables). */
export const registerProjectSettings = () => {
  const group = GROUPED_PROJECT_SETTINGS[PROJECT_SETTINGS_CATEGORY.WORK_STRUCTURE];
  if (group.some((i) => (i.key as string) === MAWESI_FIELDS_KEY)) return;
  const item = {
    key: MAWESI_FIELDS_KEY,
    i18n_label: "Campos",
    href: "/mawesi-campos",
    access: [EUserProjectRoles.ADMIN, EUserProjectRoles.MEMBER],
    highlight: (pathname: string, baseUrl: string) => pathname === `${baseUrl}/mawesi-campos/`,
  } as unknown as TProjectSettingsItem;
  group.push(item);
  PROJECT_SETTINGS_FLAT_MAP.push(item);
  (PROJECT_SETTINGS_ICONS as Record<string, unknown>)[MAWESI_FIELDS_KEY] = ListChecks;
};
