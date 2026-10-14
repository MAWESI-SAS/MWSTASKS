/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { API_BASE_URL, APIService } from "../plane";

export const PROPERTY_TYPES = ["text", "url", "number", "date", "checkbox", "select", "multi_select", "member"] as const;
export type TPropertyType = (typeof PROPERTY_TYPES)[number];
export const OPTION_TYPES: TPropertyType[] = ["select", "multi_select"];

export type TPropertyOption = { id?: string; name: string; color?: string; sort_order?: number };
export type TProperty = { id: string; name: string; type: TPropertyType; description: string; options: TPropertyOption[] };
export type TValue = string | number | boolean | string[] | null;
export type TValues = Record<string, TValue>;

class PropertyService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(ws: string, projectId: string) {
    return `/api/mawesi/workspaces/${ws}/projects/${projectId}`;
  }

  async list(ws: string, projectId: string): Promise<TProperty[]> {
    return (await this.get(`${this.base(ws, projectId)}/properties/`))?.data;
  }

  async create(ws: string, projectId: string, data: Partial<TProperty>): Promise<TProperty> {
    return (await this.post(`${this.base(ws, projectId)}/properties/`, data))?.data;
  }

  async update(ws: string, projectId: string, id: string, data: Partial<TProperty>): Promise<TProperty> {
    return (await this.patch(`${this.base(ws, projectId)}/properties/${id}/`, data))?.data;
  }

  async remove(ws: string, projectId: string, id: string): Promise<void> {
    await this.delete(`${this.base(ws, projectId)}/properties/${id}/`);
  }

  async values(ws: string, projectId: string, issueId: string): Promise<TValues> {
    return (await this.get(`${this.base(ws, projectId)}/issues/${issueId}/property-values/`))?.data;
  }

  async setValues(ws: string, projectId: string, issueId: string, values: TValues): Promise<TValues> {
    return (await this.patch(`${this.base(ws, projectId)}/issues/${issueId}/property-values/`, { values }))?.data;
  }
}

export const propertyService = new PropertyService();
