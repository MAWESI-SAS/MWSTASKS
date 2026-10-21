/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Propiedades del peek de Plane + SLA, campos propios, estimado, horas y código debajo.
 */
import type { ComponentProps } from "react";
import { PeekOverviewProperties as Upstream } from "@upstream/components/issues/peek-overview/properties";
import { CodePanel } from "../../code/code-panel";
import { EstimatePanel } from "../../estimates/estimate-panel";
import { PropertiesPanel } from "../../properties/properties-panel";
import { RecurrencePanel } from "../../recurrence/recurrence-panel";
import { SlaPanel } from "../../sla/sla-panel";
import { TemplateSubtasksButton } from "../../templates/subtasks-button";
import { WorklogPanel } from "../../worklog/worklog-panel";

export const PeekOverviewProperties = (props: ComponentProps<typeof Upstream>) => (
  <>
    <Upstream {...props} />
    <div className="mt-4 space-y-4">
      <SlaPanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} />
      <RecurrencePanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={props.disabled} />
      <TemplateSubtasksButton workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={props.disabled} />
      <PropertiesPanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={props.disabled} />
      <EstimatePanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={props.disabled} />
      <WorklogPanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={props.disabled} />
      <CodePanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} />
    </div>
  </>
);
