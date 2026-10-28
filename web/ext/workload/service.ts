/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

export type TWorkloadTask = {
  id: string;
  key: string;
  name: string;
  project_id: string;
  state: string;
  priority: string;
  start: string | null;
  end: string | null;
  remaining_minutes: number | null;
  assignee_ids: string[];
};

export type TWorkloadItem = TWorkloadTask & { share_minutes: number; days: Record<string, number> };

export type TWorkloadRow = {
  member_id: string | null;
  display_name: string;
  email: string;
  hours_per_day: number;
  capacity: Record<string, number>;
  minutes: Record<string, number>;
  tasks: Record<string, number>;
  total_minutes: number;
  capacity_minutes: number;
  items: TWorkloadItem[];
  backlog: { undated: TWorkloadTask[]; undated_count: number; overdue: TWorkloadTask[]; overdue_count: number; unestimated: number };
};

export type TWorkload = {
  from: string;
  to: string;
  today: string;
  days: Array<{ date: string; workday: boolean }>;
  default_hours_per_day: number;
  rows: TWorkloadRow[];
  truncated: boolean;
  project_ids: string[];
};

class WorkloadService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async report(ws: string, params: { from: string; to: string; project?: string; module?: string }): Promise<TWorkload> {
    const r = await this.get(`/api/mawesi/workspaces/${ws}/workload/`, { params });
    return r?.data;
  }

  async setCapacity(ws: string, memberId: string, hoursPerDay: number): Promise<{ member_id: string; hours_per_day: number }> {
    const r = await this.put(`/api/mawesi/workspaces/${ws}/workload/capacity/`, { member_id: memberId, hours_per_day: hoursPerDay });
    return r?.data;
  }
}

export const workloadService = new WorkloadService();
