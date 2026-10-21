/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Encabezado de la columna del tablero de Plane + límite de tareas (WIP) y definición de terminado, como en Azure
 * DevOps Boards. Solo con el tablero agrupado por estado y sin subgrupos. La columna se marca roja si se pasa del
 * límite (el conteo es el de Plane: las tareas que se ven con los filtros actuales).
 */
import type { ComponentProps } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { Info } from "lucide-react";
import { HeaderGroupByCard as Upstream } from "@upstream/components/issues/issue-layouts/kanban/headers/group-by-card";
import { useBoardConfig } from "../../board/use-board";
import { useT } from "../../i18n";
import { Tooltip } from "../../plane";

export * from "@upstream/components/issues/issue-layouts/kanban/headers/group-by-card";

export const HeaderGroupByCard = observer(function HeaderGroupByCard(props: ComponentProps<typeof Upstream>) {
  const t = useT();
  const { workspaceSlug, projectId } = useParams();
  const config = useBoardConfig(workspaceSlug, projectId);
  const limit = props.group_by === "state" && !props.sub_group_by ? config?.limits[props.column_id] : undefined;
  if (!limit) return <Upstream {...props} />;
  const vertical = !!props.collapsedGroups?.group_by.includes(props.column_id);
  const count = props.count || 0;
  const over = limit.wip_limit !== null && count > limit.wip_limit;
  return (
    <div
      data-mawesi="wip-header"
      data-over={over ? "true" : undefined}
      className={`flex gap-1 ${vertical ? "flex-col items-center" : "w-full flex-row items-center"} ${over ? "rounded-md bg-danger-subtle px-1" : ""}`}
    >
      <div className={vertical ? "" : "min-w-0 flex-1"}>
        <Upstream {...props} />
      </div>
      {limit.wip_limit !== null && (
        <Tooltip tooltipHeading={t("board.wip")} tooltipContent={over ? t("board.wip_over") : t("board.wip_ok")}>
          <span
            data-mawesi="wip-limit"
            className={`flex-shrink-0 rounded-sm border-[0.5px] px-1.5 text-11 font-medium ${
              over ? "border-danger-strong text-danger-primary" : "border-strong text-tertiary"
            }`}
          >
            {count}/{limit.wip_limit}
          </span>
        </Tooltip>
      )}
      {limit.definition_of_done && (
        <Tooltip
          tooltipHeading={t("board.dod")}
          tooltipContent={<span className="whitespace-pre-line">{limit.definition_of_done}</span>}
        >
          <span data-mawesi="wip-dod" className="flex-shrink-0 text-tertiary" aria-label={t("board.dod")}>
            <Info className="size-3.5" />
          </span>
        </Tooltip>
      )}
    </div>
  );
});
