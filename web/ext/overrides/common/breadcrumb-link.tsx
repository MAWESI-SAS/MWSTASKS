/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Migas de pan: se quita el paso "Modules" (lleva a la página de módulos de Plane). Las listas se ordenan
 * solo desde el árbol "Carpeta > Lista" del menú (ver folders/module-tree.tsx); el resto de migas las pinta Plane.
 */
import type { ComponentProps } from "react";
import { BreadcrumbLink as Upstream } from "@upstream/components/common/breadcrumb-link";

export * from "@upstream/components/common/breadcrumb-link";

const MODULES_PAGE = /\/projects\/[^/]+\/modules\/?$/;

export function BreadcrumbLink(props: ComponentProps<typeof Upstream>) {
  // Marca en lugar de null: el contenedor de Plane agrega el ">" a cada paso; folders/tree.css oculta el paso entero.
  if (props.href && MODULES_PAGE.test(props.href)) return <span hidden data-mawesi="hidden-crumb" />;
  return <Upstream {...props} />;
}
