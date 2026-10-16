/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import type { TKey } from "../i18n";
import { formatMinutes } from "../worklog/format";
import type { TSla, TSlaStatus } from "./service";

/** Colores por estado (clases de Plane). */
export const STATUS_CLASS: Record<TSlaStatus, string> = {
  on_track: "border-success-strong text-success-primary",
  at_risk: "border-warning-strong text-warning-primary",
  breached: "border-danger-strong text-danger-primary",
  met: "border-success-strong text-success-primary",
  missed: "border-danger-strong text-danger-primary",
  cancelled: "border-strong text-tertiary",
};

/** Texto corto: "2 h 10 min", "vencido hace 3 h", "cumplido", "incumplido". */
export const slaText = (sla: TSla, t: (k: TKey) => string): string => {
  const left = sla.remaining_minutes ?? 0;
  switch (sla.status) {
    case "on_track":
    case "at_risk":
      return `${t("sla.left")} ${formatMinutes(Math.max(0, left))}`;
    case "breached":
      return `${t("sla.late")} ${formatMinutes(Math.abs(left))}`;
    case "met":
      return t("sla.met");
    case "missed":
      return `${t("sla.missed")} (${formatMinutes(Math.abs(left))})`;
    default:
      return t("sla.cancelled");
  }
};

export const dueText = (iso: string): string =>
  new Date(iso).toLocaleString(undefined, { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
