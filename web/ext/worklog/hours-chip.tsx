/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Chip "⏱ 3 h 20 min" en la tarjeta de la tarea (tablero y lista). Si la tarea tiene estimado, muestra
 * "hecho / estimado" (rojo si se pasó) y el restante en el tooltip. Sin horas ni estimado, no aparece.
 */
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { Clock } from "lucide-react";
import { useCardEstimate } from "../estimates/use-estimate";
import { useT } from "../i18n";
import { Tooltip } from "../plane";
import { formatHours, formatMinutes } from "./format";
import { useIssueTotal } from "./totals";

type Props = { projectId: string | null; issueId: string; stateId?: string | null };

export const HoursChip = observer(function HoursChip({ projectId, issueId, stateId }: Props) {
  const t = useT();
  const { workspaceSlug } = useParams();
  const minutes = useIssueTotal(workspaceSlug, projectId, issueId);
  const estimate = useCardEstimate(workspaceSlug, projectId, issueId, `${stateId ?? ""}|${minutes}`);
  const original = estimate?.original_minutes ?? null;
  if (!minutes && original === null) return null;
  const over = original !== null && minutes > original;
  const text = original === null ? formatMinutes(minutes) : `${formatHours(minutes)} / ${formatHours(original)} h`;
  const tooltip =
    original === null
      ? formatMinutes(minutes)
      : `${t("estimate.completed")}: ${formatMinutes(minutes)} · ${t("estimate.original")}: ${formatMinutes(original)} · ${t("estimate.remaining")}: ${formatMinutes(estimate?.remaining_minutes ?? 0)}`;
  return (
    <Tooltip tooltipHeading={t("worklog.title")} tooltipContent={tooltip} renderByDefault={false}>
      <div
        data-mawesi="hours-chip"
        data-over={over ? "true" : undefined}
        className={`flex h-5 flex-shrink-0 items-center justify-center gap-1.5 overflow-hidden rounded-sm border-[0.5px] px-2.5 py-1 ${
          over ? "border-danger-strong text-danger-primary" : "border-strong"
        }`}
      >
        <Clock className="h-3 w-3 flex-shrink-0" strokeWidth={2} />
        <div className="text-caption-sm-regular">{text}</div>
      </div>
    </Tooltip>
  );
});
