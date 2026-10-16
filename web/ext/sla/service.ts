/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

export const PRIORITIES = ["urgent", "high", "medium", "low", "none"] as const;
export type TPriority = (typeof PRIORITIES)[number];

export type TSlaStatus = "on_track" | "at_risk" | "breached" | "met" | "missed" | "cancelled";

export type TSla = {
  status: TSlaStatus;
  due_at: string;
  target_minutes: number;
  elapsed_minutes: number | null;
  remaining_minutes: number | null;
};

export type TSlaPolicy = {
  id?: string;
  module_id: string | null;
  hours: Record<TPriority, number>;
  timezone: string;
  work_start: string;
  work_end: string;
  workdays: number[];
  colombia_holidays: boolean;
};

export type TStateTime = { state: string; minutes: number; business_minutes: number; visits: number };

export type TIssueSla = { sla: TSla | null; states: TStateTime[]; policy: TSlaPolicy | null };

class SlaService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(ws: string, projectId: string) {
    return `/api/mawesi/workspaces/${ws}/projects/${projectId}`;
  }

  async policy(ws: string, projectId: string): Promise<TSlaPolicy | null> {
    const r = await this.get(`${this.base(ws, projectId)}/sla/`);
    return r?.data?.policy ?? null;
  }

  async savePolicy(ws: string, projectId: string, policy: TSlaPolicy): Promise<TSlaPolicy> {
    const r = await this.put(`${this.base(ws, projectId)}/sla/`, policy);
    return r?.data?.policy;
  }

  async removePolicy(ws: string, projectId: string): Promise<void> {
    await this.delete(`${this.base(ws, projectId)}/sla/`);
  }

  async batch(ws: string, projectId: string, ids: string[]): Promise<Record<string, TSla>> {
    const r = await this.get(`${this.base(ws, projectId)}/sla/issues/`, { params: { issue_ids: ids.join(",") } });
    return r?.data ?? {};
  }

  async issue(ws: string, projectId: string, issueId: string): Promise<TIssueSla> {
    const r = await this.get(`${this.base(ws, projectId)}/issues/${issueId}/sla/`);
    return r?.data;
  }
}

export const slaService = new SlaService();
