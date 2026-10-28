/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Íconos de los ítems "Horas", "Wiki" y "Carga de trabajo" del menú del workspace; el resto de íconos los resuelve Plane.
 */
import { BookOpen, Clock, Users } from "lucide-react";
import { getSidebarNavigationItemIcon as upstreamIcon } from "@upstream/components/workspace/sidebar/helper";
import { MAWESI_NAV_KEY, MAWESI_WIKI_KEY, MAWESI_WORKLOAD_KEY } from "../../nav";

export * from "@upstream/components/workspace/sidebar/helper";

export const getSidebarNavigationItemIcon = (key: string, className: string = "") =>
  key === MAWESI_NAV_KEY ? (
    <Clock className={`size-4 flex-shrink-0 ${className}`} />
  ) : key === MAWESI_WIKI_KEY ? (
    <BookOpen className={`size-4 flex-shrink-0 ${className}`} />
  ) : key === MAWESI_WORKLOAD_KEY ? (
    <Users className={`size-4 flex-shrink-0 ${className}`} />
  ) : (
    upstreamIcon(key, className)
  );
