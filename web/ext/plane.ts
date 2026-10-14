/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * ÚNICO punto de entrada a piezas de Plane desde ext/. Si Plane mueve o renombra algo
 * (p. ej. @plane/ui → @makeplane/propel), se ajusta solo este archivo.
 */
export { Button } from "@plane/propel/button";
export { TOAST_TYPE, setToast } from "@plane/propel/toast";
export { Breadcrumbs, Header, Input, TextArea } from "@plane/ui";
// Librería de diálogos que usa ModalCore de Plane (misma versión que Plane).
export { Dialog, Transition } from "@headlessui/react";
export { useTranslation } from "@plane/i18n";
export {
  API_BASE_URL,
  EUserPermissions,
  GROUPED_PROJECT_SETTINGS,
  PROJECT_SETTINGS_CATEGORY,
  PROJECT_SETTINGS_FLAT_MAP,
  WORKSPACE_SIDEBAR_DYNAMIC_NAVIGATION_ITEMS_LINKS,
} from "@plane/constants";
export { EUserProjectRoles, EUserWorkspaceRoles } from "@plane/types";
export type { TOAuthConfigs, TProjectSettingsItem } from "@plane/types";
export { APIService } from "@/services/api.service";
export { useSearchParams } from "next/navigation";
export { useUser, useUserPermissions } from "@/hooks/store/user";
export { useMember } from "@/hooks/store/use-member";
export { useIssueDetail } from "@/hooks/store/use-issue-detail";
export { ButtonAvatars } from "@/components/dropdowns/member/avatar";
export { IssueActivityBlockComponent } from "@/components/issues/issue-detail/issue-activity/activity/actions";
export { useProject } from "@/hooks/store/use-project";
export { AppHeader } from "@/components/core/app-header";
export { ContentWrapper } from "@/components/core/content-wrapper";
// PageHead propio (marca): desde ext/ el plugin NO reemplaza módulos, así que se toma directo de overrides/.
export { PageHead } from "./overrides/core/page-title";
export { BreadcrumbLink } from "@/components/common/breadcrumb-link";
export { SettingsContentWrapper } from "@/components/settings/content-wrapper";
export { SettingsPageHeader } from "@/components/settings/page-header";
export { PROJECT_SETTINGS_ICONS } from "@/components/settings/project/sidebar/item-icon";
export { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
export { Tooltip } from "@plane/propel/tooltip";
import webPackageJson from "package.json";
/** Versión de Plane sobre la que corre MWSTASKS (para la atribución AGPL). */
export const PLANE_VERSION: string = webPackageJson.version;
