/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Tablero agrupado por estado: las columnas vacías arrancan plegadas en la franja vertical de 44px que Plane ya
 * dibuja para las columnas plegadas (idea de It's a Plan). Lo guardado en `collapsedGroups` pasa a ser "lo que la
 * persona cambió": una vacía guardada se ve abierta y una con tareas guardada se ve plegada. Así el botón de
 * plegar de Plane sigue funcionando igual en las dos direcciones.
 */
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { KanBan as Upstream } from "@upstream/components/issues/issue-layouts/kanban/default";
import type { IKanBan } from "@upstream/components/issues/issue-layouts/kanban/default";
import { useProjectState } from "../../plane";

export * from "@upstream/components/issues/issue-layouts/kanban/default";

export const KanBan = observer(function KanBan(props: IKanBan) {
  const { projectId } = useParams();
  const { getProjectStateIds } = useProjectState();
  const stateIds = getProjectStateIds(projectId);
  if (props.sub_group_by || props.group_by !== "state" || !stateIds) return <Upstream {...props} />;
  const toggled = new Set(props.collapsedGroups?.group_by ?? []);
  // Sin conteo todavía (cargando) cuenta como "con tareas": no se pliega de golpe al abrir.
  const isEmpty = (id: string) => (props.getGroupIssueCount(id, undefined, false) ?? 1) === 0;
  const collapsedGroups = {
    ...props.collapsedGroups,
    group_by: stateIds.filter((id) => isEmpty(id) !== toggled.has(id)),
  };
  return <Upstream {...props} collapsedGroups={collapsedGroups} />;
});
