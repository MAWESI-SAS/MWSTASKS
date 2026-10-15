/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Total de horas por tarea para las tarjetas del tablero y la lista. Cada tarjeta pide el suyo, pero los
 * pedidos de un mismo proyecto se juntan en uno solo (hasta 500 tareas por pedido, el máximo del servidor).
 */
import useSWR, { mutate } from "swr";
import { API_BASE_URL, APIService } from "../plane";

class TotalsService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async totals(ws: string, projectId: string, ids: string[]): Promise<Record<string, number>> {
    const r = await this.get(`/api/mawesi/workspaces/${ws}/projects/${projectId}/worklogs/totals/`, {
      params: { issue_ids: ids.join(",") },
    });
    return r?.data ?? {};
  }
}

const service = new TotalsService();
const MAX_IDS = 500;

type Batch = { waiters: Map<string, { resolve: (v: number) => void; reject: (e: unknown) => void }[]> };
const batches = new Map<string, Batch>();

const flush = async (ws: string, projectId: string) => {
  const key = `${ws}|${projectId}`;
  const batch = batches.get(key);
  batches.delete(key);
  if (!batch) return;
  const ids = [...batch.waiters.keys()];
  for (let i = 0; i < ids.length; i += MAX_IDS) {
    const chunk = ids.slice(i, i + MAX_IDS);
    try {
      const data = await service.totals(ws, projectId, chunk);
      chunk.forEach((id) => batch.waiters.get(id)!.forEach((w) => w.resolve(data[id] ?? 0)));
    } catch (e) {
      chunk.forEach((id) => batch.waiters.get(id)!.forEach((w) => w.reject(e)));
    }
  }
};

const loadTotal = (ws: string, projectId: string, issueId: string) =>
  new Promise<number>((resolve, reject) => {
    const key = `${ws}|${projectId}`;
    let batch = batches.get(key);
    if (!batch) {
      batch = { waiters: new Map() };
      batches.set(key, batch);
      window.setTimeout(() => void flush(ws, projectId), 30);
    }
    const list = batch.waiters.get(issueId) ?? [];
    list.push({ resolve, reject });
    batch.waiters.set(issueId, list);
  });

const key = (ws: string, projectId: string, issueId: string) => ["mawesi-total", ws, projectId, issueId];

export const useIssueTotal = (ws: string | undefined, projectId: string | null | undefined, issueId: string | undefined) => {
  const { data } = useSWR(ws && projectId && issueId ? key(ws, projectId, issueId) : null, () => loadTotal(ws!, projectId!, issueId!), {
    revalidateOnFocus: false,
    shouldRetryOnError: false, // guests reciben 403: sin chip
  });
  return data ?? 0;
};

/** Llamar después de guardar o borrar horas de una tarea. */
export const refreshIssueTotal = (ws: string, projectId: string, issueId: string) => mutate(key(ws, projectId, issueId));
