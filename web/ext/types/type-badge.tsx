/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { TYPE_COLORS } from "./service";
import type { TWorkItemType } from "./service";

/** Punto de color + nombre del tipo. */
export function TypeBadge({ type, className = "" }: { type: Pick<TWorkItemType, "name" | "color">; className?: string }) {
  return (
    <span className={`inline-flex min-w-0 items-center gap-1.5 ${className}`} data-mawesi="type-badge">
      <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: TYPE_COLORS[type.color] ?? TYPE_COLORS.gray }} />
      <span className="truncate">{type.name}</span>
    </span>
  );
}
