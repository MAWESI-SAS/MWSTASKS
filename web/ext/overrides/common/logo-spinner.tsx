/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Pantalla de carga: animación de MAWESI (la misma de MWSign) en lugar del GIF de Plane.
 */
import loader from "../../brand/mawesi-loader.svg?url";

export function LogoSpinner() {
  return (
    <div className="flex items-center justify-center" data-mawesi="logo-spinner">
      <img src={loader} alt="Cargando" className="h-8 w-auto object-contain sm:h-12" />
    </div>
  );
}
