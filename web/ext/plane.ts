/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * ÚNICO punto de entrada a piezas de Plane desde ext/. Si Plane mueve o renombra algo
 * (p. ej. @plane/ui → @makeplane/propel), se ajusta solo este archivo.
 */
export { Button } from "@plane/propel/button";
export { TOAST_TYPE, setToast } from "@plane/propel/toast";
export { Breadcrumbs, CustomMenu, Header, Input, TextArea } from "@plane/ui";
export { IconButton } from "@plane/propel/icon-button";
// Librería de diálogos que usa ModalCore de Plane (misma versión que Plane).
export { Dialog, Transition } from "@headlessui/react";
export { useTranslation } from "@plane/i18n";
export {
  API_BASE_URL,
  EUserPermissions,
  GROUPED_PROJECT_SETTINGS,
  GROUPED_WORKSPACE_SETTINGS,
  PROJECT_SETTINGS_CATEGORY,
  PROJECT_SETTINGS_FLAT_MAP,
  WORKSPACE_SETTINGS_ACCESS,
  WORKSPACE_SETTINGS_CATEGORY,
  WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS,
} from "@plane/constants";
export { EUserProjectRoles, EUserWorkspaceRoles } from "@plane/types";
export type { TIssuePriorities, TLogoProps, TOAuthConfigs, TProjectSettingsItem, TWorkspaceSettingsItem } from "@plane/types";
// Logo original de Plane (fuera de ext/ ese import llega a projects/logo.tsx: ver vite.ext.config.ts).
export { Logo as PlaneLogo } from "@plane/propel/emoji-icon-picker";
export { APIService } from "@/services/api.service";
export { useSearchParams } from "next/navigation";
export { useUser, useUserPermissions } from "@/hooks/store/user";
export { useMember } from "@/hooks/store/use-member";
export { useIssueDetail } from "@/hooks/store/use-issue-detail";
export { useIssues } from "@/hooks/store/use-issues";
export { useProjectState } from "@/hooks/store/use-project-state";
export { useLabel } from "@/hooks/store/use-label";
export { useIssueStoreType } from "@/hooks/use-issue-layout-store";
export { ButtonAvatars } from "@/components/dropdowns/member/avatar";
export { MemberDropdown } from "@/components/dropdowns/member/dropdown";
export { StateDropdown } from "@/components/dropdowns/state/dropdown";
export { PriorityDropdown } from "@/components/dropdowns/priority";
export { DateDropdown } from "@/components/dropdowns/date";
export { IssueService } from "@/services/issue/issue.service";
export { renderFormattedPayloadDate } from "@plane/utils";
export { IssueActivityBlockComponent } from "@/components/issues/issue-detail/issue-activity/activity/actions";
export { useProject } from "@/hooks/store/use-project";
export { useModule } from "@/hooks/store/use-module";
export { SidebarNavItem } from "@/components/sidebar/sidebar-navigation";
export { AppHeader } from "@/components/core/app-header";
export { ContentWrapper } from "@/components/core/content-wrapper";
// PageHead propio (marca): desde ext/ el plugin NO reemplaza módulos, así que se toma directo de overrides/.
export { PageHead } from "./overrides/core/page-title";
// Envuelto (oculta la miga "Modules"): ext/ usa el original por @upstream/; con "@/" el resolvedor guarda
// la resolución sin envoltorio y Plane deja de recibir el reemplazo (ver FORK.md).
export { BreadcrumbLink } from "@upstream/components/common/breadcrumb-link";
export { SettingsContentWrapper } from "@/components/settings/content-wrapper";
export { SettingsPageHeader } from "@/components/settings/page-header";
export { PROJECT_SETTINGS_ICONS } from "@/components/settings/project/sidebar/item-icon";
export { WORKSPACE_SETTINGS_ICONS } from "@/components/settings/workspace/sidebar/item-icon";
export { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
export { Tooltip } from "@plane/propel/tooltip";
import webPackageJson from "package.json";
/** Versión de Plane sobre la que corre MWSTASKS (para la atribución AGPL). */
export const PLANE_VERSION: string = webPackageJson.version;
