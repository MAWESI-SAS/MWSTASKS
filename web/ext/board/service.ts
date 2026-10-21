/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

export const CARD_COLORS = ["red", "orange", "yellow", "green", "blue", "purple", "gray"] as const;
export type TCardColor = (typeof CARD_COLORS)[number];

export type TCardConditions = {
  priorities?: string[];
  label_ids?: string[];
  state_ids?: string[];
  overdue?: boolean;
  due_in_days?: number;
  unassigned?: boolean;
};

export type TCardRule = { id?: string; name: string; color: TCardColor; conditions: TCardConditions; enabled: boolean };
export type TStateLimit = { wip_limit: number | null; definition_of_done: string };
export type TDependencyPolicy = { enforce: boolean; auto_unblock: boolean; reschedule: boolean };
export type TBoardConfig = { limits: Record<string, TStateLimit>; card_rules: TCardRule[]; dependencies?: TDependencyPolicy };

class BoardService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private url(ws: string, projectId: string) {
    return `/api/mawesi/workspaces/${ws}/projects/${projectId}/board/`;
  }

  async config(ws: string, projectId: string): Promise<TBoardConfig> {
    const r = await this.get(this.url(ws, projectId));
    return r?.data;
  }

  async save(ws: string, projectId: string, data: TBoardConfig): Promise<TBoardConfig> {
    const r = await this.put(this.url(ws, projectId), data);
    return r?.data;
  }
}

export const boardService = new BoardService();
