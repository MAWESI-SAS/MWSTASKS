/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Tipos de relación de Plane + "Empieza antes de / después de" y "Termina antes de / después de" (en Plane CE solo
 * existen en la versión paga). El backend de Plane ya los guarda; acá se ofrecen en el menú "Relaciones" de la tarea.
 * Lo que hacen está en el backend (plane_mawesi/dependencies.py). Su inverso se agrega a REVERSE_RELATIONS en
 * dependencies/register.ts.
 */
import { ArrowLeftToLine, ArrowRightToLine, ChevronsLeft, ChevronsRight } from "lucide-react";
import {
  ISSUE_RELATION_OPTIONS as PLANE_OPTIONS,
  useTimeLineRelationOptions as usePlaneOptions,
} from "@upstream/components/relations";
import type { TRelationObject } from "@upstream/components/issues/issue-detail-widgets/relations";
import { useT } from "../../i18n";
import type { TKey } from "../../i18n";

export * from "@upstream/components/relations";

export const MAWESI_RELATIONS = ["start_before", "start_after", "finish_before", "finish_after"] as const;
type TExtra = (typeof MAWESI_RELATIONS)[number];

const ICON = { start_before: ArrowRightToLine, start_after: ArrowLeftToLine, finish_before: ChevronsRight, finish_after: ChevronsLeft };

const extra = (label: (k: TExtra) => string): Record<TExtra, TRelationObject> =>
  Object.fromEntries(
    MAWESI_RELATIONS.map((key) => {
      const Icon = ICON[key];
      return [
        key,
        {
          key,
          i18n_label: label(key), // no está en el i18n de Plane: se muestra tal cual
          className: "bg-accent-subtle text-accent-primary",
          icon: (size: number) => <Icon size={size} className="text-secondary" />,
          placeholder: "None",
        } as unknown as TRelationObject,
      ];
    })
  ) as Record<TExtra, TRelationObject>;

/** Para el store de Plane (cuenta relaciones por tipo); los textos van en el hook. */
export const ISSUE_RELATION_OPTIONS = { ...PLANE_OPTIONS, ...extra((k) => k) } as typeof PLANE_OPTIONS;

export const useTimeLineRelationOptions = () => {
  const t = useT();
  const base = usePlaneOptions();
  return { ...base, ...extra((k) => t(`dep.rel.${k}` as TKey)) } as typeof base;
};
