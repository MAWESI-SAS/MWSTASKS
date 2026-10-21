/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * "Progress" del panel de una lista (módulo): Plane muestra "Invalid date. Please enter valid date." cuando la lista no
 * tiene fechas, y casi ninguna las tiene (en ClickUp las listas no llevan fechas). Sin fechas no hay gráfico: no se dibuja.
 */
import { observer } from "mobx-react";
import type { ComponentProps } from "react";
import { ModuleAnalyticsProgress as Upstream } from "@upstream/components/modules/analytics-sidebar/issue-progress";
import { useModule } from "../../plane";

export * from "@upstream/components/modules/analytics-sidebar/issue-progress";

export const ModuleAnalyticsProgress = observer(function ModuleAnalyticsProgress(props: ComponentProps<typeof Upstream>) {
  const { getModuleById } = useModule();
  const module = getModuleById(props.moduleId);
  if (module && (!module.start_date || !module.target_date)) return null;
  return <Upstream {...props} />;
});
