/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import useSWR, { mutate } from "swr";
import { createBatcher } from "../lib/batcher";
import { estimateService } from "./service";
import type { TEstimate } from "./service";

const loadEstimate = createBatcher<TEstimate | null>((ws, projectId, ids) => estimateService.batch(ws, projectId, ids), null);
const CARD = "mawesi-estimate-card";
const ISSUE = "mawesi-estimate";

/** Estimado de una tarjeta. `version` (estado + horas registradas) hace que se recalcule el restante. */
export const useCardEstimate = (ws: string | undefined, projectId: string | null | undefined, issueId: string, version: string) => {
  const { data } = useSWR(
    ws && projectId ? [CARD, ws, projectId, issueId, version] : null,
    () => loadEstimate(ws!, projectId!, issueId),
    { revalidateOnFocus: false, shouldRetryOnError: false }
  );
  return data ?? null;
};

export const useIssueEstimate = (ws: string, projectId: string, issueId: string, version: string) =>
  useSWR([ISSUE, ws, projectId, issueId, version], () => estimateService.issue(ws, projectId, issueId), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });

/** Después de cambiar el estimado: refresca la tarjeta y el panel de esa tarea. */
export const refreshEstimate = (issueId: string) =>
  mutate((key) => Array.isArray(key) && (key[0] === CARD || key[0] === ISSUE) && key[3] === issueId);
