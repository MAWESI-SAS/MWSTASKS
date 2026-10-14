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
