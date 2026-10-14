/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Pie de las pantallas de acceso. Reemplaza "Join 10,000+ teams building with Plane" y los logos de clientes de Plane.
 */
import { BRAND_TAGLINE, PRODUCT_LOCKUP } from "../../brand/brand";

export function AuthFooter() {
  return (
    <div className="flex items-center justify-center gap-2 text-13 text-tertiary" data-mawesi="auth-footer">
      <span className="font-heading font-bold text-secondary">{PRODUCT_LOCKUP}</span>
      <span aria-hidden="true">·</span>
      <span>{BRAND_TAGLINE}</span>
    </div>
  );
}
