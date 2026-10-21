/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Chip de la tarjeta (tablero y lista): "Bloqueada (2)" si algo no la deja avanzar, o "Fechas" si sus fechas chocan con
 * las de una tarea de la que depende (la línea roja del gantt de Plane pago). El tooltip dice cuáles.
 */
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR from "swr";
import { CalendarClock, Lock } from "lucide-react";
import { useT } from "../i18n";
import { createBatcher } from "../lib/batcher";
import { Tooltip } from "../plane";
import { dependencyService } from "./service";
import type { TDependencyStatus } from "./service";

const load = createBatcher<TDependencyStatus | null>((ws, projectId, ids) => dependencyService.batch(ws, projectId, ids), null);
const REFRESH_MS = 60_000; // un bloqueo se suelta cuando cambia OTRA tarea: se revisa cada minuto

type Props = { projectId: string | null; issueId: string; version: string };

export const DependencyChip = observer(function DependencyChip({ projectId, issueId, version }: Props) {
  const t = useT();
  const { workspaceSlug } = useParams();
  const { data } = useSWR(
    workspaceSlug && projectId ? ["mawesi-dependency", workspaceSlug, projectId, issueId, version] : null,
    () => load(workspaceSlug!, projectId!, issueId),
    { revalidateOnFocus: false, shouldRetryOnError: false, refreshInterval: REFRESH_MS }
  );
  if (!data) return null;
  const blocked = data.blocked_by.length > 0;
  const list = data.blocked_by.map((b) => `${b.key} · ${b.name} (${b.state})`).join("\n");
  return (
    <Tooltip
      tooltipHeading={blocked ? t("dep.blocked_by") : t("dep.conflict")}
      tooltipContent={<span className="whitespace-pre-line">{blocked ? list : t("dep.conflict_help")}</span>}
      renderByDefault={false}
    >
      <div
        data-mawesi="dependency-chip"
        data-state={blocked ? "blocked" : "conflict"}
        className={`flex h-5 flex-shrink-0 items-center justify-center gap-1.5 overflow-hidden rounded-sm border-[0.5px] px-2.5 py-1 ${
          blocked ? "border-danger-strong text-danger-primary" : "border-warning-strong text-warning-primary"
        }`}
      >
        {blocked ? <Lock className="h-3 w-3 flex-shrink-0" strokeWidth={2} /> : <CalendarClock className="h-3 w-3 flex-shrink-0" strokeWidth={2} />}
        <div className="text-caption-sm-regular">
          {blocked ? `${t("dep.blocked")} (${data.blocked_by.length})` : t("dep.dates")}
        </div>
      </div>
    </Tooltip>
  );
});
