/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
export const MAX_MINUTES = 24 * 60;

/** 90 → "1 h 30 min"; 45 → "45 min"; 120 → "2 h". */
export const formatMinutes = (total: number): string => {
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (!h) return `${m} min`;
  return m ? `${h} h ${m} min` : `${h} h`;
};

/**
 * Acepta "1h 30m", "1h", "45m", "1:30", "90" (minutos) y "1.5"/"1,5" (horas).
 * Devuelve minutos o null si no se entiende.
 */
export const parseDuration = (raw: string): number | null => {
  const s = raw.trim().toLowerCase().replace(/\s+/g, " ");
  if (!s) return null;
  let m = /^(\d+):([0-5]\d)$/.exec(s);
  if (m) return Number(m[1]) * 60 + Number(m[2]);
  m = /^(?:(\d+)\s*h(?:oras?|rs?)?)?\s*(?:(\d+)\s*m(?:in(?:utos?)?)?)?$/.exec(s);
  if (m && (m[1] || m[2])) return Number(m[1] ?? 0) * 60 + Number(m[2] ?? 0);
  m = /^(\d+)[.,](\d+)$/.exec(s);
  if (m) return Math.round(Number(`${m[1]}.${m[2]}`) * 60);
  if (/^\d+$/.test(s)) return Number(s);
  return null;
};

export const todayISO = (): string => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

/** 90 → "1,5" (horas con 1 decimal, en el formato del navegador). Para tableros donde "h min" ocupa mucho. */
export const formatHours = (total: number): string => (total / 60).toLocaleString(undefined, { maximumFractionDigits: 1 });

/** "2026-01".."2026-03" → ["2026-01", "2026-02", "2026-03"]. Vacío si el rango está al revés. */
export const monthRange = (from: string, to: string): string[] => {
  const out: string[] = [];
  let [y, m] = from.split("-").map(Number);
  const [ty, tm] = to.split("-").map(Number);
  while (y < ty || (y === ty && m <= tm)) {
    out.push(`${y}-${String(m).padStart(2, "0")}`);
    [y, m] = m === 12 ? [y + 1, 1] : [y, m + 1];
  }
  return out;
};

/** "2026-02" → "2026-02-28". */
export const monthEnd = (month: string): string => {
  const [y, m] = month.split("-").map(Number);
  return `${month}-${String(new Date(y, m, 0).getDate()).padStart(2, "0")}`;
};

/** Mes "AAAA-MM" de hoy corrido `delta` meses. */
export const monthOf = (delta = 0): string => {
  const [y, m] = todayISO().split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};
