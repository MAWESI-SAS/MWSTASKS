/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Aviso flotante abajo al centro (a la derecha tapaba el panel de horas) mientras hay un cronómetro andando (como la barra de ClickUp).
 */
import { useState } from "react";
import { Link, useParams } from "react-router";
import { Square, Timer, X } from "lucide-react";
import { useT } from "../i18n";
import { TOAST_TYPE, setToast } from "../plane";
import { refreshAfterStop, timerService, useElapsed, useTimer } from "./timer";

export const RunningTimer = () => {
  const t = useT();
  const { workspaceSlug = "" } = useParams();
  const { timer } = useTimer(workspaceSlug);
  const elapsed = useElapsed(timer?.started_at);
  const [busy, setBusy] = useState(false);
  if (!timer) return null;

  const run = async (action: "stop" | "discard") => {
    setBusy(true);
    try {
      await (action === "stop" ? timerService.stop(workspaceSlug) : timerService.discard(workspaceSlug));
      await refreshAfterStop(workspaceSlug, timer);
      if (action === "stop") setToast({ type: TOAST_TYPE.SUCCESS, title: t("timer.saved") });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("timer.error") });
    } finally {
      setBusy(false);
    }
  };

  const code = `${timer.project_identifier}-${timer.issue_sequence}`;
  return (
    <div
      data-mawesi="running-timer"
      className="fixed bottom-4 left-1/2 z-30 flex max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center gap-2 rounded-lg border border-subtle bg-surface-1 px-3 py-2 text-13 shadow-raised-200"
    >
      <Timer className="h-4 w-4 shrink-0 text-accent-primary" aria-label={t("timer.running")} />
      <Link
        to={`/${workspaceSlug}/browse/${code}/`}
        className="min-w-0 max-w-56 truncate hover:underline"
        title={timer.issue_name}
      >
        <span className="font-medium">{code}</span> {timer.issue_name}
      </Link>
      <span className="font-mono tabular-nums">{elapsed}</span>
      <button type="button" disabled={busy} onClick={() => run("stop")} aria-label={t("timer.stop")} title={t("timer.stop")} className="rounded p-1 text-danger-primary hover:bg-layer-1 disabled:opacity-50">
        <Square className="h-3.5 w-3.5 fill-current" />
      </button>
      <button type="button" disabled={busy} onClick={() => run("discard")} aria-label={t("timer.discard")} title={t("timer.discard")} className="rounded p-1 text-tertiary hover:bg-layer-1 disabled:opacity-50">
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
};
