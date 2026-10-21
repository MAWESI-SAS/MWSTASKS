/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

/** Estimado (Original Estimate), restante (Remaining Work) y hecho (Completed Work, = horas registradas). */
export type TEstimate = {
  original_minutes: number | null;
  remaining_minutes: number | null;
  remaining_is_manual: boolean;
  completed_minutes: number;
};

export type TEstimateInput = { original_minutes?: number | null; remaining_minutes?: number | null };

class EstimateService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(ws: string, projectId: string) {
    return `/api/mawesi/workspaces/${ws}/projects/${projectId}`;
  }

  async issue(ws: string, projectId: string, issueId: string): Promise<TEstimate> {
    const r = await this.get(`${this.base(ws, projectId)}/issues/${issueId}/estimate/`);
    return r?.data;
  }

  async save(ws: string, projectId: string, issueId: string, data: TEstimateInput): Promise<TEstimate> {
    const r = await this.put(`${this.base(ws, projectId)}/issues/${issueId}/estimate/`, data);
    return r?.data;
  }

  async batch(ws: string, projectId: string, ids: string[]): Promise<Record<string, TEstimate>> {
    const r = await this.get(`${this.base(ws, projectId)}/estimates/`, { params: { issue_ids: ids.join(",") } });
    return r?.data ?? {};
  }
}

export const estimateService = new EstimateService();
