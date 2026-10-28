/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Rangos de la Carga de trabajo: semana o 2 semanas desde el lunes, o el mes calendario. Fechas AAAA-MM-DD en hora local.
 */
export type TRange = "semana" | "2semanas" | "mes";

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parse = (s: string) => {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y!, m! - 1, d!);
};
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const monday = (d: Date) => addDays(d, -((d.getDay() + 6) % 7));

/** [desde, hasta] del rango que contiene `anchor`. */
export function rangeOf(anchor: string, range: TRange): [string, string] {
  const a = parse(anchor);
  if (range === "mes") return [iso(new Date(a.getFullYear(), a.getMonth(), 1)), iso(new Date(a.getFullYear(), a.getMonth() + 1, 0))];
  const start = monday(a);
  return [iso(start), iso(addDays(start, range === "semana" ? 6 : 13))];
}

/** El ancla del rango anterior (`-1`) o siguiente (`1`). */
export function shift(anchor: string, range: TRange, dir: -1 | 1): string {
  const a = parse(anchor);
  if (range === "mes") return iso(new Date(a.getFullYear(), a.getMonth() + dir, 1));
  return iso(addDays(a, dir * (range === "semana" ? 7 : 14)));
}

export const dayLabel = (date: string, locale: string): { weekday: string; day: string; month: string } => {
  const d = parse(date);
  return {
    weekday: d.toLocaleDateString(locale, { weekday: "short" }).replace(".", ""),
    day: String(d.getDate()),
    month: d.toLocaleDateString(locale, { month: "short" }).replace(".", ""),
  };
};
