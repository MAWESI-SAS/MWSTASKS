/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

export const FLOW_WINDOWS = [14, 30, 90, 180] as const;

export type TFlowStats = { count: number; avg: number | null; p50: number | null; p85: number | null };

export type TFlow = {
  days: string[];
  states: Array<{ id: string; name: string; group: string; color: string }>;
  cfd: Record<string, number[]>;
  lead_time: TFlowStats;
  cycle_time: TFlowStats;
  cycle_time_missing: number;
  throughput: Array<{ week: string; start: string; done: number }>;
  aging: Array<{ id: string; key: string; name: string; state_id: string; age_days: number }>;
  wip: number;
};

class FlowService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async flow(ws: string, projectId: string, days: number, module?: string): Promise<TFlow> {
    const r = await this.get(`/api/mawesi/workspaces/${ws}/projects/${projectId}/flow/`, {
      params: { days, ...(module ? { module } : {}) },
    });
    return r?.data;
  }
}

export const flowService = new FlowService();
