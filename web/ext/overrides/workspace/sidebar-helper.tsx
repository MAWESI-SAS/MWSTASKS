/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Ícono del ítem "Horas" del menú del workspace; el resto de íconos los resuelve Plane.
 */
import { Clock } from "lucide-react";
import { getSidebarNavigationItemIcon as upstreamIcon } from "@upstream/components/workspace/sidebar/helper";
import { MAWESI_NAV_KEY } from "../../nav";

export * from "@upstream/components/workspace/sidebar/helper";

export const getSidebarNavigationItemIcon = (key: string, className: string = "") =>
  key === MAWESI_NAV_KEY ? <Clock className={`size-4 flex-shrink-0 ${className}`} /> : upstreamIcon(key, className);
