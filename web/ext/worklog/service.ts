/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

export type TWorklog = {
  id: string;
  issue: string;
  project: string;
  member: string;
  duration_minutes: number;
  date: string;
  description: string;
  created_by: string | null;
  created_at: string;
};

export type TReportRow = {
  id: string;
  date: string;
  duration_minutes: number;
  description: string;
  member_id: string;
  member_name: string;
  project_id: string;
  project_identifier: string;
  issue_id: string;
  issue_sequence: number;
  issue_name: string;
};

export type TReport = { total_minutes: number; count: number; rows: TReportRow[] };

export type TWorklogInput = { duration_minutes: number; date: string; description?: string; member?: string };

class WorklogService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(ws: string, projectId: string, issueId: string) {
    return `/api/mawesi/workspaces/${ws}/projects/${projectId}/issues/${issueId}/worklogs/`;
  }

  async list(ws: string, projectId: string, issueId: string): Promise<TWorklog[]> {
    const r = await this.get(this.base(ws, projectId, issueId));
    return r?.data;
  }

  async create(ws: string, projectId: string, issueId: string, data: TWorklogInput): Promise<TWorklog> {
    const r = await this.post(this.base(ws, projectId, issueId), data);
    return r?.data;
  }

  async update(ws: string, projectId: string, issueId: string, id: string, data: Partial<TWorklogInput>): Promise<TWorklog> {
    const r = await this.patch(`${this.base(ws, projectId, issueId)}${id}/`, data);
    return r?.data;
  }

  async remove(ws: string, projectId: string, issueId: string, id: string): Promise<void> {
    await this.delete(`${this.base(ws, projectId, issueId)}${id}/`);
  }
}

export const REPORT_LIMIT = 5000;

class WorklogReportService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async report(ws: string, params: { from?: string; to?: string; project_id?: string }): Promise<TReport> {
    // OJO: el 2º argumento de APIService.get de Plane es config de axios (se esparce), no los query params.
    const r = await this.get(`/api/mawesi/workspaces/${ws}/worklogs/report/`, { params });
    return r?.data;
  }
}

export const worklogReportService = new WorklogReportService();

export const worklogService = new WorklogService();
