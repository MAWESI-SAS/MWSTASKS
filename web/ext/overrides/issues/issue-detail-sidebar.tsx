/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * El sidebar de Plane ocupa h-full dentro de una columna de ancho fijo. Para no editarlo, lo ponemos
 * en una columna flex: Plane toma el espacio flexible (con su propio scroll) y debajo van campos propios
 * y horas, con scroll propio si no entran.
 */
import type { ComponentProps } from "react";
import { IssueDetailsSidebar as Upstream } from "@upstream/components/issues/issue-detail/sidebar";
import { CodePanel } from "../../code/code-panel";
import { EstimatePanel } from "../../estimates/estimate-panel";
import { PropertiesPanel } from "../../properties/properties-panel";
import { RecurrencePanel } from "../../recurrence/recurrence-panel";
import { SlaPanel } from "../../sla/sla-panel";
import { TemplateSubtasksButton } from "../../templates/subtasks-button";
import { WorklogPanel } from "../../worklog/worklog-panel";

export const IssueDetailsSidebar = (props: ComponentProps<typeof Upstream>) => (
  <div className="flex h-full w-full flex-col">
    <div className="min-h-0 flex-1">
      <Upstream {...props} />
    </div>
    <div data-mawesi="sidebar-panel" className="max-h-[55%] shrink-0 space-y-4 overflow-y-auto border-t border-subtle px-6 py-4">
      <SlaPanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} />
      <RecurrencePanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={!props.isEditable} />
      <TemplateSubtasksButton workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={!props.isEditable} />
      <PropertiesPanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={!props.isEditable} />
      <EstimatePanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={!props.isEditable} />
      <WorklogPanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} disabled={!props.isEditable} />
      <CodePanel workspaceSlug={props.workspaceSlug} projectId={props.projectId} issueId={props.issueId} />
    </div>
  </div>
);
