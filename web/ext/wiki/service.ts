/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

export type TWikiPage = {
  id: string;
  name: string;
  project_id: string;
  project_identifier: string;
  project_name: string;
  owned_by: string;
  updated_at: string;
  snippet: string;
};

export type TWiki = { pages: TWikiPage[]; truncated: boolean };

class WikiService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async search(ws: string, q: string): Promise<TWiki> {
    const r = await this.get(`/api/mawesi/workspaces/${ws}/wiki/`, { params: q ? { q } : {} });
    return r?.data;
  }
}

export const wikiService = new WikiService();
