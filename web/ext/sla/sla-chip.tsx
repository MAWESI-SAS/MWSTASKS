/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Chip de SLA en la tarjeta (tablero y lista): tiempo que queda, o cuánto se pasó. Solo en tareas con SLA
 * (las de la lista que eligió la política del proyecto). Las cerradas a tiempo no muestran chip.
 */
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { AlarmClock } from "lucide-react";
import { useT } from "../i18n";
import { Tooltip } from "../plane";
import { STATUS_CLASS, dueText, slaText } from "./format";
import { useCardSla } from "./use-sla";

type Props = { projectId: string | null; issueId: string; version: string };

export const SlaChip = observer(function SlaChip({ projectId, issueId, version }: Props) {
  const t = useT();
  const { workspaceSlug } = useParams();
  const sla = useCardSla(workspaceSlug, projectId, issueId, version);
  if (!sla || sla.status === "met" || sla.status === "cancelled") return null;
  return (
    <Tooltip tooltipHeading={t("sla.title")} tooltipContent={`${t("sla.due")}: ${dueText(sla.due_at)}`} renderByDefault={false}>
      <div
        data-mawesi="sla-chip"
        data-status={sla.status}
        className={`flex h-5 flex-shrink-0 items-center justify-center gap-1.5 overflow-hidden rounded-sm border-[0.5px] px-2.5 py-1 ${STATUS_CLASS[sla.status]}`}
      >
        <AlarmClock className="h-3 w-3 flex-shrink-0" strokeWidth={2} />
        <div className="text-caption-sm-regular">{slaText(sla, t)}</div>
      </div>
    </Tooltip>
  );
});
