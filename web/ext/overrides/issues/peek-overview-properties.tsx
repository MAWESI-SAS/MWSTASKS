/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Propiedades del peek de Plane + campos propios + horas debajo.
 */
import type { ComponentProps } from "react";
import { PeekOverviewProperties as Upstream } from "@upstream/components/issues/peek-overview/properties";
import { PropertiesPanel } from "../../properties/properties-panel";
import { WorklogPanel } from "../../worklog/worklog-panel";

export const PeekOverviewProperties = (props: ComponentProps<typeof Upstream>) => (
  <>
    <Upstream {...props} />
    <div className="mt-4 space-y-4">
      <PropertiesPanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={props.disabled} />
      <WorklogPanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={props.disabled} />
    </div>
  </>
);
