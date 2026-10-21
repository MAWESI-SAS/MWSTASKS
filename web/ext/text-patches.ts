/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Reemplazos de texto que hace el plugin al compilar (sin editar archivos de Plane): textos de marca y, al final, unos
 * pocos ajustes de diseño que Plane deja fijos en el código (anchos, valores por defecto).
 * `file`: final de la ruta del módulo. Cada reemplazo debe encontrarse al menos una vez: si Plane cambia el texto,
 * el build FALLA (la actualización avisa). Solo textos visibles: no se tocan avisos de copyright ni licencias.
 */
import { APP_TITLE, PRODUCT_LOCKUP, PRODUCT_NAME } from "./brand/brand";

type Rule = [from: string | RegExp, to: string];
export type TextPatch = { file: string; rules: Rule[] };

/** "Plane" como palabra suelta (no PlaneLogo, no plane.so, no @plane/...). */
const WORD = /(?<![\w.@/-])Plane(?![\w-])/g;

export const TEXT_PATCHES: TextPatch[] = [
  {
    file: "apps/web/app/root.tsx",
    rules: [
      ['"Plane | Simple, extensible, open-source project management tool."', JSON.stringify(APP_TITLE)],
      ['<meta name="application-name" content="Plane" />', `<meta name="application-name" content="${PRODUCT_NAME}" />`],
      [/"Plane - Modern project management"/g, JSON.stringify(PRODUCT_LOCKUP)],
      ['{ name: "twitter:site", content: "@planepowers" },', ""],
    ],
  },
  {
    file: "packages/constants/dist/index.mjs",
    rules: [[/"Plane \| Simple, extensible, open-source project management tool\."/g, JSON.stringify(APP_TITLE)]],
  },
  { file: "apps/web/core/components/account/auth-forms/auth-header.tsx", rules: [[WORD, PRODUCT_NAME]] },
  { file: "apps/web/core/components/auth-screens/header.tsx", rules: [['" - Plane"', `" - ${PRODUCT_NAME}"`]] },
  { file: "apps/web/app/(all)/sign-up/layout.tsx", rules: [["Sign up - Plane", `Sign up - ${PRODUCT_NAME}`]] },
  { file: "apps/web/app/(all)/accounts/forgot-password/layout.tsx", rules: [["- Plane", `- ${PRODUCT_NAME}`]] },
  { file: "apps/web/app/(all)/accounts/set-password/layout.tsx", rules: [["- Plane", `- ${PRODUCT_NAME}`]] },
  { file: "apps/web/app/(all)/accounts/reset-password/layout.tsx", rules: [["- Plane", `- ${PRODUCT_NAME}`]] },
  { file: "apps/web/core/components/onboarding/steps/role/root.tsx", rules: [[WORD, PRODUCT_NAME]] },
  { file: "apps/web/core/components/onboarding/steps/profile/root.tsx", rules: [[WORD, PRODUCT_NAME]] },
  { file: "apps/web/core/components/onboarding/steps/usecase/root.tsx", rules: [[WORD, PRODUCT_NAME]] },
  { file: "apps/web/core/components/onboarding/steps/team/root.tsx", rules: [["Work in plane", `Work in ${PRODUCT_NAME}`], [WORD, PRODUCT_NAME]] },
  { file: "apps/web/core/components/onboarding/tour/root.tsx", rules: [[WORD, PRODUCT_NAME]] },
  { file: "apps/web/core/components/onboarding/tour/sidebar.tsx", rules: [[WORD, PRODUCT_NAME]] },
  { file: "apps/web/core/components/instance/not-ready-view.tsx", rules: [["Welcome to Plane", `Bienvenido a ${PRODUCT_NAME}`]] },
  // Actor de sistema en el historial ("Plane creó…").
  // (onboarding/invite-members.tsx y common/activity/user.tsx también dicen "Plane", pero en v1.4.2 nadie los importa.)
  {
    file: "apps/web/core/components/issues/issue-detail/issue-activity/activity/actions/helpers/issue-creator.tsx",
    rules: [['|| "Plane"', `|| "${PRODUCT_NAME}"`]],
  },
  { file: "apps/web/core/components/issues/peek-overview/properties.tsx", rules: [['? "Plane"', `? "${PRODUCT_NAME}"`]] },

  // ---- Diseño ----
  // Tablero: columnas de 350px (en 1440px entraban 3 de 7). 280px y las vacías de 200px (siguen recibiendo tarjetas).
  {
    file: "apps/web/core/components/issues/issue-layouts/kanban/default.tsx",
    rules: [["groupByVisibilityToggle.showIssues ? `w-[350px]` : ``", "groupByVisibilityToggle.showIssues ? (issueLength ? `w-[280px]` : `w-[200px]`) : ``"]],
  },
  { file: "apps/web/core/components/issues/issue-layouts/kanban/swimlanes.tsx", rules: [["flex w-[350px] flex-shrink-0", "flex w-[280px] flex-shrink-0"]] },
  // Panel de la lista cerrado por defecto (ocupaba un cuarto de la pantalla). Quien lo abre, lo encuentra abierto después.
  {
    file: "apps/web/app/(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/modules/(detail)/[moduleId]/page.tsx",
    rules: [['useLocalStorage("module_sidebar_collapsed", "false")', 'useLocalStorage("module_sidebar_collapsed", "true")']],
  },
  {
    file: "apps/web/app/(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/modules/(detail)/header.tsx",
    rules: [['useLocalStorage("module_sidebar_collapsed", "false")', 'useLocalStorage("module_sidebar_collapsed", "true")']],
  },
];

/** Traducciones (todas las lenguas): "Plane" suelto → MWSTASKS. Se exige al menos un reemplazo en en y es. */
export const LOCALE_FILE = /\/i18n\/(?:src\/)?locales\/([A-Za-z-]+)\/[^/]+\.json$/;
export const LOCALE_RULE: Rule = [WORD, PRODUCT_NAME];
