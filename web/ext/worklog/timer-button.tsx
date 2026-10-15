/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Botón ▶ / ■ del cronómetro dentro del panel de horas de una tarea.
 */
import { useState } from "react";
import { Play, Square } from "lucide-react";
import { useT } from "../i18n";
import { TOAST_TYPE, setToast } from "../plane";
import { refreshAfterStop, timerService, useElapsed, useTimer } from "./timer";

type Props = { workspaceSlug: string; projectId: string; issueId: string; onStopped: () => Promise<void> };

export const TimerButton = ({ workspaceSlug, projectId, issueId, onStopped }: Props) => {
  const t = useT();
  const { timer, refresh } = useTimer(workspaceSlug);
  const [busy, setBusy] = useState(false);
  const here = timer?.issue_id === issueId;
  const elapsed = useElapsed(here ? timer?.started_at : undefined);

  const toggle = async () => {
    setBusy(true);
    try {
      if (here) {
        await timerService.stop(workspaceSlug);
        await onStopped();
        setToast({ type: TOAST_TYPE.SUCCESS, title: t("timer.saved") });
      } else {
        const previous = timer;
        await timerService.start(workspaceSlug, projectId, issueId);
        if (previous) await refreshAfterStop(workspaceSlug, previous); // el anterior se guardó solo
      }
      await refresh();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("timer.error") });
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      disabled={busy}
      onClick={toggle}
      data-mawesi={here ? "timer-stop" : "timer-start"}
      className={`flex items-center gap-1 rounded-md px-1 py-1 text-13 disabled:opacity-50 ${
        here ? "font-medium text-danger-primary hover:bg-layer-1" : "text-secondary hover:bg-layer-1 hover:text-primary"
      }`}
    >
      {here ? <Square className="h-3.5 w-3.5 fill-current" /> : <Play className="h-3.5 w-3.5" />}
      {here ? `${t("timer.stop")} · ${elapsed}` : t("timer.start")}
    </button>
  );
};
