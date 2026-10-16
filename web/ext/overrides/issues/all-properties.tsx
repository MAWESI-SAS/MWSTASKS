/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Propiedades de la tarjeta (tablero y lista) de Plane + chips de horas y de SLA al final, en la misma fila.
 * El contenedor de Plane queda con `contents` para que sus chips y el nuestro compartan el mismo flex.
 */
import { IssueProperties as Upstream } from "@upstream/components/issues/issue-layouts/properties/all-properties";
import type { IIssueProperties } from "@upstream/components/issues/issue-layouts/properties/all-properties";
import { SlaChip } from "../../sla/sla-chip";
import { HoursChip } from "../../worklog/hours-chip";

export * from "@upstream/components/issues/issue-layouts/properties/all-properties";

export const IssueProperties = (props: IIssueProperties) => {
  // Mismo corte que Plane: sin propiedades visibles no dibuja nada (y no debe quedar un div vacío).
  if (!props.displayProperties || !props.issue.project_id || props.isEpic) return <Upstream {...props} />;
  return (
    <div className={props.className}>
      <Upstream {...props} className="contents" />
      <HoursChip projectId={props.issue.project_id} issueId={props.issue.id} />
      <SlaChip projectId={props.issue.project_id} issueId={props.issue.id} version={`${props.issue.state_id}|${props.issue.priority}`} />
    </div>
  );
};
