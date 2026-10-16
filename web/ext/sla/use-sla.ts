/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import useSWR from "swr";
import { createBatcher } from "../lib/batcher";
import { slaService } from "./service";
import type { TSla } from "./service";

const loadSla = createBatcher<TSla | null>((ws, projectId, ids) => slaService.batch(ws, projectId, ids), null);
const REFRESH_MS = 60_000; // el plazo corre solo: se recalcula cada minuto

/** SLA de una tarjeta. `version` (estado + prioridad) hace que se recalcule al cambiarlos. */
export const useCardSla = (ws: string | undefined, projectId: string | null | undefined, issueId: string, version: string) => {
  const { data } = useSWR(
    ws && projectId ? ["mawesi-sla", ws, projectId, issueId, version] : null,
    () => loadSla(ws!, projectId!, issueId),
    { revalidateOnFocus: false, shouldRetryOnError: false, refreshInterval: REFRESH_MS }
  );
  return data ?? null;
};

export const useIssueSla = (ws: string, projectId: string, issueId: string, version: string) =>
  useSWR(["mawesi-sla-issue", ws, projectId, issueId, version], () => slaService.issue(ws, projectId, issueId), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
    refreshInterval: REFRESH_MS,
  });
