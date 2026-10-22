/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Tipos de tarea con sus propios campos (backend plane_mawesi/types.py).
 */
import { API_BASE_URL, APIService } from "../plane";

export const TYPE_COLORS = {
  gray: "#8b8d98",
  red: "#e5484d",
  orange: "#f76b15",
  yellow: "#d6a400",
  green: "#30a46c",
  blue: "#0090ff",
  purple: "#8e4ec6",
  pink: "#d6409f",
} as const;
export type TTypeColor = keyof typeof TYPE_COLORS;

export type TWorkItemType = {
  id: string;
  name: string;
  description: string;
  color: TTypeColor;
  is_default: boolean;
  property_ids: string[];
  module_ids: string[];
};

/** Tipo efectivo de una tarea: source "issue" (elegido), "list" (el de su lista), "project" (el del proyecto). */
export type TIssueType = { type_id: string | null; source: "issue" | "list" | "project" | null; property_ids: string[] | null };

class TypeService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(ws: string, projectId: string) {
    return `/api/mawesi/workspaces/${ws}/projects/${projectId}`;
  }

  async list(ws: string, projectId: string): Promise<TWorkItemType[]> {
    return (await this.get(`${this.base(ws, projectId)}/types/`))?.data;
  }

  async create(ws: string, projectId: string, data: Partial<TWorkItemType>): Promise<TWorkItemType> {
    return (await this.post(`${this.base(ws, projectId)}/types/`, data))?.data;
  }

  async update(ws: string, projectId: string, id: string, data: Partial<TWorkItemType>): Promise<TWorkItemType> {
    return (await this.patch(`${this.base(ws, projectId)}/types/${id}/`, data))?.data;
  }

  async remove(ws: string, projectId: string, id: string): Promise<void> {
    await this.delete(`${this.base(ws, projectId)}/types/${id}/`);
  }

  async ofIssue(ws: string, projectId: string, issueId: string): Promise<TIssueType> {
    return (await this.get(`${this.base(ws, projectId)}/issues/${issueId}/type/`))?.data;
  }

  async setOfIssue(ws: string, projectId: string, issueId: string, typeId: string | null): Promise<TIssueType> {
    return (await this.put(`${this.base(ws, projectId)}/issues/${issueId}/type/`, { type_id: typeId }))?.data;
  }
}

export const typeService = new TypeService();
