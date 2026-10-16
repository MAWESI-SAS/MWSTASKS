/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Rutas propias. Plane fusiona por archivo de layout (app/routes/helper.ts → mergeRoutes), así que para
 * quedar dentro del workspace repetimos la cadena de layouts de Plane (LAYOUT_CHAIN). Si Plane renombra
 * alguno, scripts/assemble-web.sh falla antes de compilar.
 * Rutas de archivo relativas a apps/web/app (appDirectory de React Router).
 */
import { layout, route } from "@react-router/dev/routes";
import type { RouteConfigEntry } from "@react-router/dev/routes";

export const LAYOUT_CHAIN = [
  "./(all)/layout.tsx",
  "./(all)/[workspaceSlug]/layout.tsx",
  "./(all)/[workspaceSlug]/(projects)/layout.tsx",
] as const;

export const PROJECT_LAYOUT = "./(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/layout.tsx";

export const SETTINGS_CHAIN = [
  "./(all)/[workspaceSlug]/(settings)/layout.tsx",
  "./(all)/[workspaceSlug]/(settings)/settings/projects/layout.tsx",
  "./(all)/[workspaceSlug]/(settings)/settings/projects/[projectId]/layout.tsx",
] as const;

export const extendedRoutes: RouteConfigEntry[] = [
  route("mawesi/ping", "../ext/pages/ping.tsx"),
  layout(LAYOUT_CHAIN[0], [
    layout(LAYOUT_CHAIN[1], [
      layout(LAYOUT_CHAIN[2], [
        layout("../ext/pages/worklog-report/layout.tsx", [
          route(":workspaceSlug/mawesi/horas", "../ext/pages/worklog-report/page.tsx"),
        ]),
        layout("../ext/pages/wiki/layout.tsx", [
          route(":workspaceSlug/mawesi/wiki", "../ext/pages/wiki/page.tsx"),
        ]),
        // Dentro del layout del proyecto: ProjectAuthWrapper controla el acceso y carga estados y módulos.
        layout(PROJECT_LAYOUT, [
          layout("../ext/pages/table/layout.tsx", [
            route(":workspaceSlug/projects/:projectId/mawesi-tabla", "../ext/pages/table/page.tsx"),
          ]),
        ]),
      ]),
      layout(SETTINGS_CHAIN[0], [
        layout(SETTINGS_CHAIN[1], [
          layout(SETTINGS_CHAIN[2], [
            route(":workspaceSlug/settings/projects/:projectId/mawesi-campos", "../ext/pages/properties-settings/page.tsx"),
          ]),
        ]),
      ]),
    ]),
  ]),
];
