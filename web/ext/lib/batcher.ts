/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Junta los pedidos "por tarea" de un mismo proyecto en uno solo (hasta 500 ids por pedido, el máximo del
 * servidor). Cada tarjeta del tablero pide lo suyo; en 30 ms se manda un único pedido por proyecto.
 */
const MAX_IDS = 500;
const WINDOW_MS = 30;

type Fetch<T> = (ws: string, projectId: string, ids: string[]) => Promise<Record<string, T>>;
type Waiter<T> = { resolve: (v: T) => void; reject: (e: unknown) => void };

export const createBatcher = <T>(fetchMany: Fetch<T>, fallback: T) => {
  const batches = new Map<string, Map<string, Waiter<T>[]>>();

  const flush = async (ws: string, projectId: string) => {
    const key = `${ws}|${projectId}`;
    const waiters = batches.get(key);
    batches.delete(key);
    if (!waiters) return;
    const ids = [...waiters.keys()];
    for (let i = 0; i < ids.length; i += MAX_IDS) {
      const chunk = ids.slice(i, i + MAX_IDS);
      try {
        const data = await fetchMany(ws, projectId, chunk);
        chunk.forEach((id) => waiters.get(id)!.forEach((w) => w.resolve(data[id] ?? fallback)));
      } catch (e) {
        chunk.forEach((id) => waiters.get(id)!.forEach((w) => w.reject(e)));
      }
    }
  };

  return (ws: string, projectId: string, issueId: string) =>
    new Promise<T>((resolve, reject) => {
      const key = `${ws}|${projectId}`;
      let waiters = batches.get(key);
      if (!waiters) {
        waiters = new Map();
        batches.set(key, waiters);
        window.setTimeout(() => void flush(ws, projectId), WINDOW_MS);
      }
      const list = waiters.get(issueId) ?? [];
      list.push({ resolve, reject });
      waiters.set(issueId, list);
    });
};
