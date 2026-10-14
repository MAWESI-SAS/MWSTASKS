/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Insignia del menú lateral: "MWSTASKS" con la atribución a Plane (AGPL) en el tooltip, sin la invitación a
 * comprar planes pagos de Plane. Lleva al código fuente.
 */
import { useT } from "../../i18n";
import { PLANE_VERSION, Tooltip } from "../../plane";
import { PRODUCT_LOCKUP, PRODUCT_NAME, SOURCE_URL, UPSTREAM_NAME } from "../../brand/brand";

export function WorkspaceEditionBadge() {
  const t = useT();
  return (
    <Tooltip tooltipContent={`${PRODUCT_LOCKUP} · ${t("brand.based_on")} ${UPSTREAM_NAME} v${PLANE_VERSION} (AGPL-3.0)`}>
      <a
        href={SOURCE_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex h-8 items-center rounded-md px-3 font-heading text-13 font-bold text-accent-primary hover:bg-layer-transparent-hover"
        data-mawesi="edition-badge"
      >
        {PRODUCT_NAME}
      </a>
    </Tooltip>
  );
}
