/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Sección "Relaciones" del detalle y del peek: abierta al entrar a cada tarea (Plane la deja cerrada; las
 * relaciones migradas de ClickUp quedaban escondidas). Si la persona la cierra, queda cerrada hasta abrir otra tarea.
 */
import { useEffect, type ComponentProps } from "react";
import { RelationsCollapsible as Upstream } from "@upstream/components/issues/issue-detail-widgets/relations/root";
import { useIssueDetail } from "../../plane";

export * from "@upstream/components/issues/issue-detail-widgets/relations/root";

export function RelationsCollapsible(props: ComponentProps<typeof Upstream>) {
  const { openWidgets, toggleOpenWidget } = useIssueDetail(props.issueServiceType);
  useEffect(() => {
    if (!openWidgets.includes("relations")) toggleOpenWidget("relations");
    // Solo al cambiar de tarea: depender de openWidgets la volvería a abrir cada vez que se cierra.
  }, [props.issueId]);
  return <Upstream {...props} />;
}
