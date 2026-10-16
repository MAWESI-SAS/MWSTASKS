/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";
import type { TPriority } from "../sla/service";

export const TRIGGERS = ["created", "added_to_list", "state", "priority"] as const;
export type TTrigger = (typeof TRIGGERS)[number];

export type TActions = {
  assignee_ids?: string[];
  state_id?: string;
  priority?: TPriority;
  label_ids?: string[];
  due_in_days?: number;
  template_id?: string;
};

export type TRule = {
  id?: string;
  name: string;
  enabled: boolean;
  trigger: TTrigger;
  trigger_value: string;
  module_id: string | null;
  actions: TActions;
  runs?: number;
  last_run_at?: string | null;
};

export type TOption = { id: string; name: string; group?: string };
export type TRulesData = { rules: TRule[]; states: TOption[]; labels: TOption[]; templates: TOption[] };

class AutomationsService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(ws: string, projectId: string) {
    return `/api/mawesi/workspaces/${ws}/projects/${projectId}/automations/`;
  }

  async list(ws: string, projectId: string): Promise<TRulesData> {
    const r = await this.get(this.base(ws, projectId));
    return r?.data;
  }

  async create(ws: string, projectId: string, data: TRule): Promise<TRule> {
    const r = await this.post(this.base(ws, projectId), data);
    return r?.data;
  }

  async update(ws: string, projectId: string, id: string, data: Partial<TRule>): Promise<TRule> {
    const r = await this.patch(`${this.base(ws, projectId)}${id}/`, data);
    return r?.data;
  }

  async remove(ws: string, projectId: string, id: string): Promise<void> {
    await this.delete(`${this.base(ws, projectId)}${id}/`);
  }
}

export const automationsService = new AutomationsService();
