/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * CSV pensado para Excel en español: separador ";", coma decimal y BOM UTF-8 (tildes correctas).
 */
import type { TReportRow } from "./service";

export const cell = (v: string | number) => {
  const s = String(v ?? "");
  return /[";\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export const reportToCSV = (rows: TReportRow[]): string => {
  const head = ["Fecha", "Proyecto", "Tarea", "Título", "Persona", "Minutos", "Horas", "Nota"];
  const lines = rows.map((r) =>
    [
      r.date,
      r.project_identifier,
      `${r.project_identifier}-${r.issue_sequence}`,
      r.issue_name,
      r.member_name,
      r.duration_minutes,
      (r.duration_minutes / 60).toFixed(2).replace(".", ","),
      r.description,
    ]
      .map(cell)
      .join(";")
  );
  return "﻿" + [head.join(";"), ...lines].join("\r\n");
};

/** Tabla grupo × mes en horas (coma decimal), con fila de totales. */
export const summaryToCSV = (head: string, months: string[], rows: Array<{ label: string; cells: Record<string, number>; total: number }>): string => {
  const hours = (mins = 0) => (mins / 60).toFixed(2).replace(".", ",");
  const lines = rows.map((r) => [r.label, ...months.map((m) => hours(r.cells[m])), hours(r.total)].map(cell).join(";"));
  return "\ufeff" + [[head, ...months, "Total"].map(cell).join(";"), ...lines].join("\r\n");
};

export const downloadCSV = (content: string, filename: string) => {
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};
