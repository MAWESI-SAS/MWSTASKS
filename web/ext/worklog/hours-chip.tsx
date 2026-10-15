/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Chip "⏱ 3 h 20 min" en la tarjeta de la tarea (tablero y lista). Solo aparece si hay horas.
 */
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { Clock } from "lucide-react";
import { useT } from "../i18n";
import { Tooltip } from "../plane";
import { formatMinutes } from "./format";
import { useIssueTotal } from "./totals";

export const HoursChip = observer(function HoursChip({ projectId, issueId }: { projectId: string | null; issueId: string }) {
  const t = useT();
  const { workspaceSlug } = useParams();
  const minutes = useIssueTotal(workspaceSlug, projectId, issueId);
  if (!minutes) return null;
  return (
    <Tooltip tooltipHeading={t("worklog.title")} tooltipContent={formatMinutes(minutes)} renderByDefault={false}>
      <div
        data-mawesi="hours-chip"
        className="flex h-5 flex-shrink-0 items-center justify-center gap-1.5 overflow-hidden rounded-sm border-[0.5px] border-strong px-2.5 py-1"
      >
        <Clock className="h-3 w-3 flex-shrink-0" strokeWidth={2} />
        <div className="text-caption-sm-regular">{formatMinutes(minutes)}</div>
      </div>
    </Tooltip>
  );
});
