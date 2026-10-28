/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Entrada "Horas" en la sección Workspace del menú lateral. Se agrega al arreglo exportado de Plane
 * (WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS) al cargar la app, sin editar Plane.
 * labelTranslationKey no existe en el i18n de Plane: i18next muestra la clave tal cual ("Horas").
 */
import { AlarmClock, FolderGit2, LayoutTemplate, ListChecks, Shapes, SquareKanban, Zap } from "lucide-react";
import {
  EUserProjectRoles,
  EUserWorkspaceRoles,
  GROUPED_PROJECT_SETTINGS,
  GROUPED_WORKSPACE_SETTINGS,
  PROJECT_SETTINGS_CATEGORY,
  PROJECT_SETTINGS_FLAT_MAP,
  PROJECT_SETTINGS_ICONS,
  WORKSPACE_SETTINGS_ACCESS,
  WORKSPACE_SETTINGS_CATEGORY,
  WORKSPACE_SETTINGS_ICONS,
  WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS,
} from "./plane";
import type { TProjectSettingsItem, TWorkspaceSettingsItem } from "./plane";

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

export const MAWESI_WIKI_KEY = "mawesi_wiki";

/** "Wiki" en la misma sección: buscador sobre las Páginas de todos los proyectos. */
export const registerWikiNav = () => {
  if (WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS.some((i) => i.key === MAWESI_WIKI_KEY)) return;
  WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS.push({
    key: MAWESI_WIKI_KEY,
    labelTranslationKey: "Wiki",
    href: "/mawesi/wiki/",
    access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER],
    highlight: (pathname: string, url: string) => pathname.includes(url),
  });
};

export const MAWESI_WORKLOAD_KEY = "mawesi_workload";

/** "Carga de trabajo" (la vista Workload de ClickUp): horas por persona y día de todos los proyectos. */
export const registerWorkloadNav = () => {
  if (WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS.some((i) => i.key === MAWESI_WORKLOAD_KEY)) return;
  WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS.push({
    key: MAWESI_WORKLOAD_KEY,
    labelTranslationKey: "Carga de trabajo",
    href: "/mawesi/carga/",
    access: [EUserWorkspaceRoles.ADMIN, EUserWorkspaceRoles.MEMBER],
    highlight: (pathname: string, url: string) => pathname.includes(url),
  });
};

export const MAWESI_FIELDS_KEY = "mawesi_fields";
export const MAWESI_TYPES_KEY = "mawesi_types";
export const MAWESI_SLA_KEY = "mawesi_sla";
export const MAWESI_TEMPLATES_KEY = "mawesi_templates";
export const MAWESI_RULES_KEY = "mawesi_rules";
export const MAWESI_BOARD_KEY = "mawesi_board";

/** Ítems propios en Configuración del proyecto → Estructura de trabajo (objetos exportados de Plane, mutables). */
const SETTINGS: Array<{ key: string; label: string; slug: string; icon: unknown }> = [
  { key: MAWESI_FIELDS_KEY, label: "Campos", slug: "mawesi-campos", icon: ListChecks },
  { key: MAWESI_TYPES_KEY, label: "Tipos", slug: "mawesi-tipos", icon: Shapes },
  { key: MAWESI_SLA_KEY, label: "SLA", slug: "mawesi-sla", icon: AlarmClock },
  { key: MAWESI_TEMPLATES_KEY, label: "Plantillas", slug: "mawesi-plantillas", icon: LayoutTemplate },
  { key: MAWESI_RULES_KEY, label: "Reglas", slug: "mawesi-reglas", icon: Zap },
  { key: MAWESI_BOARD_KEY, label: "Tablero", slug: "mawesi-tablero", icon: SquareKanban },
];

export const registerProjectSettings = () => {
  const group = GROUPED_PROJECT_SETTINGS[PROJECT_SETTINGS_CATEGORY.WORK_STRUCTURE];
  for (const s of SETTINGS) {
    if (group.some((i) => (i.key as string) === s.key)) continue;
    const item = {
      key: s.key,
      i18n_label: s.label,
      href: `/${s.slug}`,
      access: [EUserProjectRoles.ADMIN, EUserProjectRoles.MEMBER],
      highlight: (pathname: string, baseUrl: string) => pathname === `${baseUrl}/${s.slug}/`,
    } as unknown as TProjectSettingsItem;
    group.push(item);
    PROJECT_SETTINGS_FLAT_MAP.push(item);
    (PROJECT_SETTINGS_ICONS as Record<string, unknown>)[s.key] = s.icon;
  }
};

export const MAWESI_REPOS_KEY = "mawesi_repos";
export const MAWESI_REPOS_HREF = "/settings/mawesi-repos";

/** "Repositorios" en Configuración del workspace → Desarrollador (junto a Webhooks). Solo admins del workspace:
 * también se agrega a WORKSPACE_SETTINGS_ACCESS, que el layout de Plane consulta por la URL. */
export const registerWorkspaceSettings = () => {
  const group = GROUPED_WORKSPACE_SETTINGS[WORKSPACE_SETTINGS_CATEGORY.DEVELOPER];
  if (group.some((i) => (i.key as string) === MAWESI_REPOS_KEY)) return;
  group.push({
    key: MAWESI_REPOS_KEY,
    i18n_label: "Repositorios",
    href: MAWESI_REPOS_HREF,
    access: [EUserWorkspaceRoles.ADMIN],
    highlight: (pathname: string, baseUrl: string) => pathname === `${baseUrl}${MAWESI_REPOS_HREF}/`,
  } as unknown as TWorkspaceSettingsItem);
  (WORKSPACE_SETTINGS_ACCESS as Record<string, unknown>)[MAWESI_REPOS_HREF] = [EUserWorkspaceRoles.ADMIN];
  (WORKSPACE_SETTINGS_ICONS as Record<string, unknown>)[MAWESI_REPOS_KEY] = FolderGit2;
};
