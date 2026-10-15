/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Cronómetro (▶ de ClickUp). El servidor guarda cuándo arrancó: sigue andando aunque se cierre el navegador.
 */
import { useEffect, useState } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { API_BASE_URL, APIService } from "../plane";
import { refreshIssueTotal } from "./totals";

export type TTimer = {
  id: string;
  started_at: string;
  description: string;
  issue_id: string;
  project_id: string;
  issue_name: string;
  issue_sequence: number;
  project_identifier: string;
};

class TimerService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async current(ws: string): Promise<TTimer | null> {
    const r = await this.get(`/api/mawesi/workspaces/${ws}/timer/`);
    return r?.data?.timer ?? null;
  }

  async start(ws: string, projectId: string, issueId: string): Promise<TTimer> {
    const r = await this.post(`/api/mawesi/workspaces/${ws}/projects/${projectId}/issues/${issueId}/timer/start/`, {});
    return r?.data?.timer;
  }

  async stop(ws: string): Promise<void> {
    await this.post(`/api/mawesi/workspaces/${ws}/timer/stop/`, {});
  }

  async discard(ws: string): Promise<void> {
    await this.delete(`/api/mawesi/workspaces/${ws}/timer/`);
  }
}

export const timerService = new TimerService();

const key = (ws: string) => ["mawesi-timer", ws];

/** Cronómetro de quien mira. Se revisa cada minuto por si lo arrancó en otra pestaña. */
export const useTimer = (ws: string) => {
  const { data, mutate } = useSWR(ws ? key(ws) : null, () => timerService.current(ws), {
    refreshInterval: 60_000,
    revalidateOnFocus: true,
  });
  return { timer: data ?? null, refresh: () => mutate() };
};

/** Después de parar: refresca el cronómetro y las horas de la tarea (en cualquier panel abierto). */
export const refreshAfterStop = async (ws: string, timer: TTimer | null) => {
  await globalMutate(key(ws));
  if (timer) {
    await globalMutate(["mawesi-worklogs", ws, timer.project_id, timer.issue_id]);
    await refreshIssueTotal(ws, timer.project_id, timer.issue_id);
  }
};

/** "0:05:09" desde started_at, actualizado cada segundo. */
export const useElapsed = (startedAt: string | undefined) => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!startedAt) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [startedAt]);
  if (!startedAt) return "";
  const secs = Math.max(0, Math.floor((now - new Date(startedAt).getTime()) / 1000));
  const h = Math.floor(secs / 3600);
  const m = String(Math.floor((secs % 3600) / 60)).padStart(2, "0");
  const s = String(secs % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
};
