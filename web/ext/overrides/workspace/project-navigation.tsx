/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Ítems del proyecto en el menú lateral de Plane + "Tabla", "Capacidad" y "Flujo" (vistas propias) + árbol
 * "Carpeta > Lista".
 * Usa la prop additionalNavigationItems que Plane ya trae (y que nadie le pasa en CE).
 * El árbol reemplaza al ítem "Módulos": `folders/tree.css` lo oculta dentro de [data-mawesi=project-nav].
 */
import { useCallback } from "react";
import type { ComponentProps } from "react";
import { ChartArea, Gauge, Table2 } from "lucide-react";
import { ProjectNavigation as Upstream } from "@upstream/components/workspace/sidebar/project-navigation";
import { ModuleTree } from "../../folders/module-tree";
import { useT } from "../../i18n";
import { EUserPermissions } from "../../plane";

export * from "@upstream/components/workspace/sidebar/project-navigation";

export const ProjectNavigation = (props: ComponentProps<typeof Upstream>) => {
  const t = useT();
  const labels = { table: t("table.title"), capacity: t("capacity.title"), flow: t("flow.title") };
  const extra = useCallback(
    (ws: string, pid: string) => [
      ...(props.additionalNavigationItems?.(ws, pid) ?? []),
      // sortOrder: Work items es 1; Tabla justo después. Capacidad y Flujo después de Cycles (2) y Modules (3).
      ...[
        { key: "mawesi_table", name: labels.table, slug: "mawesi-tabla", icon: Table2, sortOrder: 1.5 },
        { key: "mawesi_capacity", name: labels.capacity, slug: "mawesi-capacidad", icon: Gauge, sortOrder: 3.5 },
        { key: "mawesi_flow", name: labels.flow, slug: "mawesi-flujo", icon: ChartArea, sortOrder: 3.6 },
      ].map(({ slug, ...item }) => ({
        ...item,
        i18n_key: item.name, // no está en el i18n de Plane: se muestra tal cual
        href: `/${ws}/projects/${pid}/${slug}`,
        access: [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
        shouldRender: true,
      })),
    ],
    [labels.table, labels.capacity, labels.flow, props.additionalNavigationItems]
  );
  return (
    <>
      <div className="contents" data-mawesi="project-nav">
        <Upstream {...props} additionalNavigationItems={extra} />
      </div>
      <ModuleTree workspaceSlug={props.workspaceSlug} projectId={props.projectId} />
    </>
  );
};
