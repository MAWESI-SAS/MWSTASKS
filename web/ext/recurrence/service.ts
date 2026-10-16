/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

export const FREQUENCIES = ["daily", "weekdays", "weekly", "monthly"] as const;
export type TFrequency = (typeof FREQUENCIES)[number];
export type TTrigger = "complete" | "schedule";

export type TRecurrence = {
  id: string;
  frequency: TFrequency;
  interval: number;
  trigger: TTrigger;
  occurrences: number;
  next_start: string | null;
  next_target: string | null;
};

export type TRecurrenceInput = Pick<TRecurrence, "frequency" | "interval" | "trigger">;

class RecurrenceService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private url(ws: string, projectId: string, issueId: string) {
    return `/api/mawesi/workspaces/${ws}/projects/${projectId}/issues/${issueId}/recurrence/`;
  }

  async read(ws: string, projectId: string, issueId: string): Promise<TRecurrence | null> {
    const r = await this.get(this.url(ws, projectId, issueId));
    return r?.data?.recurrence ?? null;
  }

  async write(ws: string, projectId: string, issueId: string, data: TRecurrenceInput): Promise<TRecurrence> {
    const r = await this.put(this.url(ws, projectId, issueId), data);
    return r?.data?.recurrence;
  }

  async remove(ws: string, projectId: string, issueId: string): Promise<void> {
    await this.delete(this.url(ws, projectId, issueId));
  }
}

export const recurrenceService = new RecurrenceService();
