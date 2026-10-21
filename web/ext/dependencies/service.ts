/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

export type TBlocker = { id: string; key: string; name: string; kind: "blocked_by" | "start_before" | "finish_before"; state: string };
export type TDependencyStatus = { blocked_by: TBlocker[]; conflict: boolean };

class DependencyService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async batch(ws: string, projectId: string, ids: string[]): Promise<Record<string, TDependencyStatus>> {
    const r = await this.get(`/api/mawesi/workspaces/${ws}/projects/${projectId}/dependencies/`, { params: { issue_ids: ids.join(",") } });
    return r?.data ?? {};
  }
}

export const dependencyService = new DependencyService();
