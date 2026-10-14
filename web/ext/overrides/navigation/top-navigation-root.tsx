/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Barra superior de Plane dentro de .mawesi-topbar (display: contents → no cambia el layout), para que sus
 * colores sean blancos sobre el gradiente MAWESI (ver theme/shell.css).
 */
import { TopNavigationRoot as Upstream } from "@upstream/components/navigation/top-navigation-root";

export const TopNavigationRoot = () => (
  <div className="mawesi-topbar" data-mawesi="topbar">
    <Upstream />
  </div>
);
