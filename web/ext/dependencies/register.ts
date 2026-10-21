/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Inversos de los tipos "empieza/termina antes/después" en el mapa de Plane (REVERSE_RELATIONS, objeto exportado y
 * mutable): el store lo usa para mostrar la relación en las dos tareas sin recargar. Y el aviso de cambios frenados.
 */
import { REVERSE_RELATIONS } from "../plane";
import { installDependencyToast } from "./blocked-toast";

const PAIRS: Array<[string, string]> = [
  ["start_before", "start_after"],
  ["finish_before", "finish_after"],
];

export const registerDependencies = (title: () => string) => {
  const map = REVERSE_RELATIONS as Record<string, string>;
  for (const [a, b] of PAIRS) {
    map[a] = b;
    map[b] = a;
  }
  installDependencyToast(title);
};
