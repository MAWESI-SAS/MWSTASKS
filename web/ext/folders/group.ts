/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Arma el árbol "Carpeta > Lista" con los módulos de un proyecto. La migración nombra cada módulo
 * "Carpeta / Lista" (Plane no tiene carpetas); un módulo sin " / " es una lista suelta.
 */
export type TModuleLite = { id: string; name: string; created_at?: string | Date | null; created_by?: string | null };
export type TList = { id: string; name: string; created_by?: string | null };
export type TFolder = { name: string; lists: TList[] };
export type TTree = { folders: TFolder[]; loose: TList[] };

export const SEP = " / ";
/** Largo máximo de cada parte: el nombre del módulo (Plane: 255) es "Carpeta / Lista". */
export const MAX_PART = 120;

/** Nombre del módulo de una lista; sin carpeta es una lista suelta. */
export const moduleName = (folder: string, list: string): string =>
  folder.trim() ? `${folder.trim()}${SEP}${list.trim()}` : list.trim();

/** Una parte válida no está vacía ni lleva el separador, ni empieza o termina en "/" (partiría mal el árbol). */
export const isValidPart = (value: string): boolean => {
  const v = value.trim();
  return v.length > 0 && v.length <= MAX_PART && !v.includes(SEP) && !v.startsWith("/") && !v.endsWith("/");
};

export const groupModules = (modules: TModuleLite[]): TTree => {
  // Orden de creación = orden de ClickUp (la migración los crea en ese orden).
  const ordered = [...modules].sort((a, b) => String(a.created_at ?? "").localeCompare(String(b.created_at ?? "")));
  const folders = new Map<string, TFolder>();
  const loose: TTree["loose"] = [];
  for (const m of ordered) {
    const i = m.name.indexOf(SEP);
    if (i <= 0) {
      loose.push({ id: m.id, name: m.name, created_by: m.created_by });
      continue;
    }
    const folder = m.name.slice(0, i).trim();
    if (!folders.has(folder)) folders.set(folder, { name: folder, lists: [] });
    folders.get(folder)!.lists.push({ id: m.id, name: m.name.slice(i + SEP.length).trim(), created_by: m.created_by });
  }
  return { folders: [...folders.values()], loose };
};
