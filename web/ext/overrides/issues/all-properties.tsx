/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Propiedades de la tarjeta (tablero y lista) de Plane + chips de horas y de SLA al final, en la misma fila.
 * El contenedor de Plane queda con `contents` para que sus chips y el nuestro compartan el mismo flex.
 * Como Linear: solo se dibujan las propiedades con valor (Plane pinta un botón vacío por cada una) y, dentro de una
 * lista o un ciclo, no se repite esa misma lista o ciclo en cada tarjeta. El estado solo se oculta cuando el tablero
 * o la lista ya están agrupados por estado (la columna o el grupo lo dicen).
 */
import { observer } from "mobx-react";
import { IssueProperties as Upstream } from "@upstream/components/issues/issue-layouts/properties/all-properties";
import type { IIssueProperties } from "@upstream/components/issues/issue-layouts/properties/all-properties";
import { useParams } from "react-router";
import { useIssueStoreType, useIssues } from "../../plane";
import { SlaChip } from "../../sla/sla-chip";
import { HoursChip } from "../../worklog/hours-chip";

export * from "@upstream/components/issues/issue-layouts/properties/all-properties";

type Props = IIssueProperties["displayProperties"];

function filledProperties(
  displayProperties: NonNullable<Props>,
  issue: IIssueProperties["issue"],
  route: { moduleId?: string; cycleId?: string; groupedByState: boolean }
): NonNullable<Props> {
  return {
    ...displayProperties,
    state: !!displayProperties.state && !route.groupedByState,
    priority: !!displayProperties.priority && !!issue.priority && issue.priority !== "none",
    // Plane une las dos fechas en un rango solo cuando existen ambas: cada una se puede apagar por separado.
    start_date: !!displayProperties.start_date && !!issue.start_date,
    due_date: !!displayProperties.due_date && !!issue.target_date,
    assignee: !!displayProperties.assignee && !!issue.assignee_ids?.length,
    labels: !!displayProperties.labels && !!issue.label_ids?.length,
    estimate: !!displayProperties.estimate && !!issue.estimate_point,
    modules: !!displayProperties.modules && !!issue.module_ids?.length && !route.moduleId,
    cycle: !!displayProperties.cycle && !!issue.cycle_id && !route.cycleId,
  };
}

export const IssueProperties = observer(function IssueProperties(props: IIssueProperties) {
  const { moduleId, cycleId } = useParams();
  const { issuesFilter } = useIssues(useIssueStoreType());
  const groupedByState = issuesFilter?.issueFilters?.displayFilters?.group_by === "state";
  // Mismo corte que Plane: sin propiedades visibles no dibuja nada (y no debe quedar un div vacío).
  if (!props.displayProperties || !props.issue.project_id || props.isEpic) return <Upstream {...props} />;
  const displayProperties = filledProperties(props.displayProperties, props.issue, { moduleId, cycleId, groupedByState });
  return (
    <div className={props.className}>
      <Upstream {...props} displayProperties={displayProperties} className="contents" />
      <HoursChip projectId={props.issue.project_id} issueId={props.issue.id} />
      <SlaChip projectId={props.issue.project_id} issueId={props.issue.id} version={`${props.issue.state_id}|${props.issue.priority}`} />
    </div>
  );
});
