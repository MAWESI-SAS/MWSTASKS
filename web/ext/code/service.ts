/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

export type TCodeProvider = "github" | "azure";

export type TCodeRepo = {
  id: string;
  provider: TCodeProvider;
  path: string;
  url: string;
  enabled: boolean;
  last_synced_at: string | null;
  last_error: string;
  links_found: number;
  token_configured: boolean;
  new_links?: number;
};

export type TCodeRepos = { repos: TCodeRepo[]; tokens: Record<TCodeProvider, boolean>; sync_minutes: number };

export type TCodeLink = {
  id: string;
  kind: "commit" | "pr";
  external_id: string;
  url: string;
  title: string;
  author: string;
  state: string;
  branch: string;
  happened_at: string;
  closed_issue: boolean;
  repo: string;
  provider: TCodeProvider;
};

class CodeService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private repos(ws: string) {
    return `/api/mawesi/workspaces/${ws}/code-repos/`;
  }

  async list(ws: string): Promise<TCodeRepos> {
    const r = await this.get(this.repos(ws));
    return r?.data;
  }

  async add(ws: string, provider: TCodeProvider, path: string): Promise<TCodeRepo> {
    const r = await this.post(this.repos(ws), { provider, path });
    return r?.data;
  }

  async setEnabled(ws: string, id: string, enabled: boolean): Promise<TCodeRepo> {
    const r = await this.patch(`${this.repos(ws)}${id}/`, { enabled });
    return r?.data;
  }

  async remove(ws: string, id: string): Promise<void> {
    await this.delete(`${this.repos(ws)}${id}/`);
  }

  async sync(ws: string, id: string): Promise<TCodeRepo> {
    const r = await this.post(`${this.repos(ws)}${id}/sync/`, {});
    return r?.data;
  }

  async links(ws: string, projectId: string, issueId: string): Promise<TCodeLink[]> {
    const r = await this.get(`/api/mawesi/workspaces/${ws}/projects/${projectId}/issues/${issueId}/code-links/`);
    return r?.data ?? [];
  }
}

export const codeService = new CodeService();
