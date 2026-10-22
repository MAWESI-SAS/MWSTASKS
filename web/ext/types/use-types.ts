/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import useSWR from "swr";
import { typeService } from "./service";

export const useProjectTypes = (ws: string, projectId: string) => {
  const { data, isLoading, mutate } = useSWR(ws && projectId ? ["mawesi-types", ws, projectId] : null, () => typeService.list(ws, projectId));
  return { types: data ?? [], isLoading, mutate };
};

export const useIssueType = (ws: string, projectId: string, issueId: string) => {
  const { data, mutate } = useSWR(ws && projectId && issueId ? ["mawesi-issue-type", ws, projectId, issueId] : null, () =>
    typeService.ofIssue(ws, projectId, issueId)
  );
  return { issueType: data, mutate };
};
