/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import useSWR from "swr";
import { API_BASE_URL, APIService } from "../plane";
import type { TPriority } from "../sla/service";

export type TTemplateSubtask = { name: string; priority: TPriority; checklist: string[] };

export type TTemplate = {
  id?: string;
  name: string;
  priority: TPriority;
  module_id: string | null;
  assignee_ids: string[];
  checklist: string[];
  subtasks: TTemplateSubtask[];
  add_parent_name: boolean;
  created_by?: string | null;
};

export type TApplyResult = { issue_id: string; sequence_id: number; subtasks: number };

class TemplatesService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(ws: string, projectId: string) {
    return `/api/mawesi/workspaces/${ws}/projects/${projectId}/templates/`;
  }

  async list(ws: string, projectId: string): Promise<TTemplate[]> {
    const r = await this.get(this.base(ws, projectId));
    return r?.data ?? [];
  }

  async create(ws: string, projectId: string, data: TTemplate): Promise<TTemplate> {
    const r = await this.post(this.base(ws, projectId), data);
    return r?.data;
  }

  async update(ws: string, projectId: string, id: string, data: TTemplate): Promise<TTemplate> {
    const r = await this.patch(`${this.base(ws, projectId)}${id}/`, data);
    return r?.data;
  }

  async remove(ws: string, projectId: string, id: string): Promise<void> {
    await this.delete(`${this.base(ws, projectId)}${id}/`);
  }

  /** Con issue_id agrega las subtareas a esa tarea; con name crea la tarea (en module_id si viene). */
  async apply(ws: string, projectId: string, id: string, body: { issue_id?: string; name?: string; module_id?: string }): Promise<TApplyResult> {
    const r = await this.post(`${this.base(ws, projectId)}${id}/apply/`, body);
    return r?.data;
  }
}

export const templatesService = new TemplatesService();

/** Misma clave SWR en la configuración, el árbol y el detalle: guardar una plantilla actualiza todo. */
export const useTemplates = (ws: string, projectId: string, enabled = true) =>
  useSWR(enabled && ws && projectId ? ["mawesi-templates", ws, projectId] : null, () => templatesService.list(ws, projectId), {
    revalidateOnFocus: false,
  });
