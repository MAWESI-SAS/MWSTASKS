/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

export type TCycleOption = { id: string; name: string; start: string; end: string };

export type TCapacityMember = {
  member_id: string;
  display_name: string;
  avatar_url: string;
  hours_per_day: number;
  days_off: string[];
  days_total: number;
  days_left: number;
  capacity_minutes: number;
  capacity_left_minutes: number;
  remaining_minutes: number;
  unestimated: number;
  open_items: number;
  completed_minutes: number;
};

export type TCapacityReport = {
  cycle: TCycleOption;
  today: string;
  team_days_off: string[];
  team_days_left: number;
  members: TCapacityMember[];
  unassigned: { remaining_minutes: number; unestimated: number; count: number };
  totals: { capacity_left_minutes: number; remaining_minutes: number; open_items: number; unestimated: number };
};

export type TCapacityInput = {
  team_days_off?: string[];
  members?: Array<{ member_id: string; hours_per_day: number; days_off: string[] }>;
};

class CapacityService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(ws: string, projectId: string) {
    return `/api/mawesi/workspaces/${ws}/projects/${projectId}`;
  }

  async cycles(ws: string, projectId: string): Promise<{ cycles: TCycleOption[]; current_id: string | null }> {
    const r = await this.get(`${this.base(ws, projectId)}/capacity/cycles/`);
    return r?.data;
  }

  async report(ws: string, projectId: string, cycleId: string): Promise<TCapacityReport> {
    const r = await this.get(`${this.base(ws, projectId)}/cycles/${cycleId}/capacity/`);
    return r?.data;
  }

  async save(ws: string, projectId: string, cycleId: string, data: TCapacityInput): Promise<TCapacityReport> {
    const r = await this.put(`${this.base(ws, projectId)}/cycles/${cycleId}/capacity/`, data);
    return r?.data;
  }
}

export const capacityService = new CapacityService();
