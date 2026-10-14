/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import useSWR from "swr";
import { propertyService } from "./service";

export const useProjectProperties = (ws: string, projectId: string) => {
  const { data, isLoading, mutate } = useSWR(ws && projectId ? ["mawesi-props", ws, projectId] : null, () =>
    propertyService.list(ws, projectId)
  );
  return { properties: data ?? [], isLoading, mutate };
};

export const useIssueValues = (ws: string, projectId: string, issueId: string) => {
  const { data, mutate } = useSWR(ws && projectId && issueId ? ["mawesi-values", ws, projectId, issueId] : null, () =>
    propertyService.values(ws, projectId, issueId)
  );
  return { values: data ?? {}, mutate };
};
