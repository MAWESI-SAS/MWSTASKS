/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Panel "Estimado" del detalle de la tarea (como Original Estimate / Remaining / Completed de Azure DevOps):
 * estimado y restante se escriben (1h 30m, 1:30, 1.5…); lo hecho son las horas registradas. Si el restante no se
 * corrige a mano, es estimado − hecho. La barra muestra hecho contra hecho + restante.
 */
import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { RotateCcw } from "lucide-react";
import { useT } from "../i18n";
import { Input, TOAST_TYPE, setToast, useIssueDetail } from "../plane";
import { apiError } from "../lib/api-error";
import { formatMinutes, parseDuration } from "../worklog/format";
import { useIssueTotal } from "../worklog/totals";
import { estimateService } from "./service";
import type { TEstimateInput } from "./service";
import { refreshEstimate, useIssueEstimate } from "./use-estimate";

type Props = { workspaceSlug: string; projectId: string; issueId: string; disabled?: boolean };

const asText = (m: number | null | undefined) => (m === null || m === undefined ? "" : formatMinutes(m));

export const EstimatePanel = observer(function EstimatePanel({ workspaceSlug, projectId, issueId, disabled }: Props) {
  const t = useT();
  const { issue } = useIssueDetail();
  const state = issue.getIssueById(issueId)?.state_id ?? "";
  const total = useIssueTotal(workspaceSlug, projectId, issueId);
  const { data, mutate } = useIssueEstimate(workspaceSlug, projectId, issueId, `${state}|${total}`);
  const [original, setOriginal] = useState("");
  const [remaining, setRemaining] = useState("");

  useEffect(() => {
    setOriginal(asText(data?.original_minutes));
    setRemaining(data?.remaining_is_manual ? asText(data.remaining_minutes) : "");
  }, [data?.original_minutes, data?.remaining_minutes, data?.remaining_is_manual]);

  if (!data) return null;

  const save = async (patch: TEstimateInput) => {
    try {
      await mutate(await estimateService.save(workspaceSlug, projectId, issueId, patch), { revalidate: false });
      void refreshEstimate(issueId);
    } catch (err) {
      setToast({ type: TOAST_TYPE.ERROR, title: apiError(err, t("estimate.error")) });
      setOriginal(asText(data.original_minutes));
      setRemaining(data.remaining_is_manual ? asText(data.remaining_minutes) : "");
    }
  };

  /** Al salir del campo: vacío borra; si no se entiende, vuelve a lo guardado. */
  const commit = (raw: string, key: keyof TEstimateInput, saved: number | null) => {
    const value = raw.trim() ? parseDuration(raw) : null;
    if (raw.trim() && value === null) {
      setToast({ type: TOAST_TYPE.ERROR, title: t("estimate.err_duration") });
      return key === "original_minutes" ? setOriginal(asText(saved)) : setRemaining(asText(saved));
    }
    if (value !== saved) void save({ [key]: value });
  };

  const done = data.completed_minutes;
  const left = data.remaining_minutes ?? 0;
  const pct = done + left > 0 ? Math.min(100, Math.round((done / (done + left)) * 100)) : 0;
  const over = data.original_minutes !== null && done > data.original_minutes;

  return (
    <div data-mawesi="estimate-panel" className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h5 className="text-body-xs-medium">{t("estimate.title")}</h5>
        {data.original_minutes !== null && (
          <span className={`text-11 ${over ? "text-danger-primary" : "text-tertiary"}`} data-mawesi="estimate-summary">
            {over ? t("estimate.over") : `${pct}% ${t("estimate.done_pct")}`}
          </span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2 text-13">
        <label className="space-y-0.5">
          <span className="block text-11 text-tertiary">{t("estimate.original")}</span>
          <Input
            name="estimate-original"
            value={original}
            placeholder="—"
            disabled={disabled}
            onChange={(e) => setOriginal(e.target.value)}
            onBlur={() => commit(original, "original_minutes", data.original_minutes)}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            className="w-full"
          />
        </label>
        <label className="space-y-0.5">
          <span className="flex items-center gap-1 text-11 text-tertiary">
            {t("estimate.remaining")}
            {data.remaining_is_manual && !disabled && (
              <button
                type="button"
                title={t("estimate.reset_remaining")}
                aria-label={t("estimate.reset_remaining")}
                onClick={() => void save({ remaining_minutes: null })}
                className="rounded p-0.5 hover:bg-layer-1"
                data-mawesi="estimate-reset"
              >
                <RotateCcw className="size-3" />
              </button>
            )}
          </span>
          <Input
            name="estimate-remaining"
            value={remaining}
            placeholder={data.remaining_minutes === null ? "—" : asText(data.remaining_minutes)}
            disabled={disabled}
            onChange={(e) => setRemaining(e.target.value)}
            onBlur={() => commit(remaining, "remaining_minutes", data.remaining_is_manual ? data.remaining_minutes : null)}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            className="w-full"
          />
        </label>
        <div className="space-y-0.5">
          <span className="block text-11 text-tertiary">{t("estimate.completed")}</span>
          <div className="flex h-8 items-center px-1 font-medium" data-mawesi="estimate-completed">
            {formatMinutes(done)}
          </div>
        </div>
      </div>
      {data.original_minutes !== null && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-layer-1" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className={`h-full rounded-full ${over ? "bg-danger-primary" : "bg-accent-primary"}`} style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
});
