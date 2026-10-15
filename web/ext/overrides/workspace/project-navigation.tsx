/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Ítems del proyecto en el menú lateral de Plane + "Tabla" (vista propia) + árbol "Carpeta > Lista".
 * Usa la prop additionalNavigationItems que Plane ya trae (y que nadie le pasa en CE).
 */
import { useCallback } from "react";
import type { ComponentProps } from "react";
import { Table2 } from "lucide-react";
import { ProjectNavigation as Upstream } from "@upstream/components/workspace/sidebar/project-navigation";
import { ModuleTree } from "../../folders/module-tree";
import { useT } from "../../i18n";
import { EUserPermissions } from "../../plane";

export * from "@upstream/components/workspace/sidebar/project-navigation";

export const ProjectNavigation = (props: ComponentProps<typeof Upstream>) => {
  const t = useT();
  const label = t("table.title");
  const extra = useCallback(
    (ws: string, pid: string) => [
      ...(props.additionalNavigationItems?.(ws, pid) ?? []),
      {
        key: "mawesi_table",
        name: label,
        i18n_key: label, // no está en el i18n de Plane: se muestra tal cual
        href: `/${ws}/projects/${pid}/mawesi-tabla`,
        icon: Table2,
        access: [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
        shouldRender: true,
        sortOrder: 1.5, // justo después de Work items
      },
    ],
    [label, props.additionalNavigationItems]
  );
  return (
    <>
      <Upstream {...props} additionalNavigationItems={extra} />
      <ModuleTree workspaceSlug={props.workspaceSlug} projectId={props.projectId} />
    </>
  );
};
