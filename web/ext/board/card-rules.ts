/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Qué regla de color le toca a una tarjeta (card styling de Azure DevOps). Todas las condiciones de una regla deben
 * cumplirse; gana la primera regla que coincide. Las tareas terminadas o canceladas no se pintan.
 */
import type { TCardRule } from "./service";

export type TCardIssue = {
  priority?: string | null;
  label_ids?: string[];
  state_id?: string | null;
  assignee_ids?: string[];
  target_date?: string | null;
};

/** "AAAA-MM-DD" de hoy en la hora local del navegador. */
const localISO = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

export const daysUntil = (due: string, today = new Date()): number => {
  const a = new Date(`${localISO(today)}T00:00:00`);
  const b = new Date(`${due.slice(0, 10)}T00:00:00`);
  return Math.round((b.getTime() - a.getTime()) / 86_400_000);
};

export const matches = (rule: TCardRule, issue: TCardIssue, today = new Date()): boolean => {
  if (!rule.enabled) return false;
  const c = rule.conditions;
  if (c.priorities?.length && !c.priorities.includes(issue.priority ?? "none")) return false;
  if (c.label_ids?.length && !c.label_ids.some((id) => issue.label_ids?.includes(id))) return false;
  if (c.state_ids?.length && !c.state_ids.includes(issue.state_id ?? "")) return false;
  if (c.unassigned && (issue.assignee_ids?.length ?? 0) > 0) return false;
  if (c.overdue && !(issue.target_date && daysUntil(issue.target_date, today) < 0)) return false;
  if (c.due_in_days !== undefined && c.due_in_days !== null) {
    if (!issue.target_date) return false;
    const d = daysUntil(issue.target_date, today);
    if (d < 0 || d > c.due_in_days) return false;
  }
  return true;
};

export const ruleFor = (rules: TCardRule[], issue: TCardIssue, closed: boolean): TCardRule | null =>
  closed ? null : (rules.find((r) => matches(r, issue)) ?? null);
