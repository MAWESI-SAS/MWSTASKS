/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

class ProjectLogoService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private url(ws: string, projectId: string) {
    return `/api/mawesi/workspaces/${ws}/projects/${projectId}/logo/`;
  }

  async upload(ws: string, projectId: string, image: Blob, name: string): Promise<void> {
    const form = new FormData();
    form.append("file", image, name);
    await this.post(this.url(ws, projectId), form);
  }

  async remove(ws: string, projectId: string): Promise<void> {
    await this.delete(this.url(ws, projectId));
  }
}

export const projectLogoService = new ProjectLogoService();
