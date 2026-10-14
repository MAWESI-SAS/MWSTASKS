/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * CSV pensado para Excel en español: separador ";", coma decimal y BOM UTF-8 (tildes correctas).
 */
import type { TReportRow } from "./service";

const cell = (v: string | number) => {
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
