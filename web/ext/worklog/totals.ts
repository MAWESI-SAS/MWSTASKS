/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Total de horas por tarea para las tarjetas del tablero y la lista. Cada tarjeta pide el suyo, pero los
 * pedidos de un mismo proyecto se juntan en uno solo (lib/batcher.ts).
 */
import useSWR, { mutate } from "swr";
import { createBatcher } from "../lib/batcher";
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
const loadTotal = createBatcher<number>((ws, projectId, ids) => service.totals(ws, projectId, ids), 0);

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
