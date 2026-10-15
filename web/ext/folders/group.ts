/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Arma el árbol "Carpeta > Lista" con los módulos de un proyecto. La migración nombra cada módulo
 * "Carpeta / Lista" (Plane no tiene carpetas); un módulo sin " / " es una lista suelta.
 */
export type TModuleLite = { id: string; name: string; created_at?: string | Date | null; sort_order?: number };
export type TFolder = { name: string; lists: { id: string; name: string }[] };
export type TTree = { folders: TFolder[]; loose: { id: string; name: string }[] };

const SEP = " / ";

export const groupModules = (modules: TModuleLite[]): TTree => {
  // Orden de creación = orden de ClickUp (la migración los crea en ese orden).
  const ordered = [...modules].sort((a, b) => String(a.created_at ?? "").localeCompare(String(b.created_at ?? "")));
  const folders = new Map<string, TFolder>();
  const loose: TTree["loose"] = [];
  for (const m of ordered) {
    const i = m.name.indexOf(SEP);
    if (i <= 0) {
      loose.push({ id: m.id, name: m.name });
      continue;
    }
    const folder = m.name.slice(0, i).trim();
    if (!folders.has(folder)) folders.set(folder, { name: folder, lists: [] });
    folders.get(folder)!.lists.push({ id: m.id, name: m.name.slice(i + SEP.length).trim() });
  }
  return { folders: [...folders.values()], loose };
};
