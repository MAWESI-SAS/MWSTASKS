/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Barra superior de Plane dentro de .mawesi-topbar (display: contents → no cambia el layout), para que sus
 * colores sean blancos sobre el gradiente MAWESI (ver theme/shell.css).
 * También monta el aviso del cronómetro: la barra está en todas las pantallas del workspace.
 */
import { TopNavigationRoot as Upstream } from "@upstream/components/navigation/top-navigation-root";
import { RunningTimer } from "../../worklog/running-timer";

// El aviso va fuera de .mawesi-topbar (que pinta todo en blanco); es fixed, así que no cambia el layout.
export const TopNavigationRoot = () => (
  <>
    <div className="mawesi-topbar" data-mawesi="topbar">
      <Upstream />
    </div>
    <RunningTimer />
  </>
);
