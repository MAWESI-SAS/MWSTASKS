/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService, IssueService } from "../plane";
import type { TIssuePriorities } from "../plane";

export type TPropValue = string | number | boolean | string[] | null;

export type TTableRow = {
  id: string;
  sequence_id: number;
  name: string;
  state_id: string | null;
  priority: TIssuePriorities;
  start_date: string | null;
  target_date: string | null;
  parent_id: string | null;
  assignee_ids: string[];
  module_ids: string[];
  minutes: number;
  values: Record<string, TPropValue>;
};

export type TTableProperty = {
  id: string;
  name: string;
  type: "text" | "url" | "number" | "date" | "checkbox" | "select" | "multi_select" | "member";
  options: { id: string; name: string; color: string }[];
};

export type TTable = {
  rows: TTableRow[];
  truncated: boolean;
  states: Record<string, { name: string; color: string; group: string }>;
  properties: TTableProperty[];
};

class TableService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async table(ws: string, projectId: string, params: { module?: string; closed?: "1" }): Promise<TTable> {
    const r = await this.get(`/api/mawesi/workspaces/${ws}/projects/${projectId}/table/`, { params });
    return r?.data;
  }
}

export const tableService = new TableService();

/** Cambios de la Tabla: por la API de Plane (historial, avisos y reglas igual que en el detalle). */
export const issueService = new IssueService();
