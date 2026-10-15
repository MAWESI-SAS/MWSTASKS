/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Árbol "Carpeta > Lista" debajo de cada proyecto en el menú lateral (como la jerarquía de ClickUp).
 * Cada lista abre su módulo. Lo abierto/cerrado se recuerda por navegador.
 */
import { useState } from "react";
import { observer } from "mobx-react";
import { Link, useLocation } from "react-router";
import useSWR from "swr";
import { ChevronRight, Folder, FolderOpen, List } from "lucide-react";
import { useT } from "../i18n";
import { SidebarNavItem, useModule } from "../plane";
import { groupModules } from "./group";

type Props = { workspaceSlug: string; projectId: string };

const STORAGE = "mawesi-tree-open";

const readOpen = (): Record<string, boolean> => {
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE) || "{}");
  } catch {
    return {};
  }
};

const writeOpen = (value: Record<string, boolean>) => {
  try {
    window.localStorage.setItem(STORAGE, JSON.stringify(value));
  } catch {
    // modo privado: solo se pierde el recuerdo
  }
};

export const ModuleTree = observer(function ModuleTree({ workspaceSlug, projectId }: Props) {
  const t = useT();
  const moduleStore = useModule();
  const { pathname } = useLocation();
  const [open, setOpen] = useState<Record<string, boolean>>(readOpen);
  // Plane solo carga los módulos del proyecto abierto: una llamada trae los de todo el workspace.
  useSWR(workspaceSlug ? ["mawesi-ws-modules", workspaceSlug] : null, () => moduleStore.fetchWorkspaceModules(workspaceSlug), {
    revalidateOnFocus: false,
  });
  const modules = moduleStore.getProjectModuleDetails(projectId) ?? [];
  if (modules.length === 0) return null;
  const tree = groupModules(modules);

  const toggle = (folder: string) => {
    const k = `${projectId}:${folder}`;
    const next = { ...open, [k]: !open[k] };
    setOpen(next);
    writeOpen(next);
  };

  const listLink = (l: { id: string; name: string }, indent: boolean) => {
    const href = `/${workspaceSlug}/projects/${projectId}/modules/${l.id}`;
    return (
      <Link key={l.id} to={href} title={l.name} data-mawesi="tree-list">
        <SidebarNavItem isActive={pathname.includes(l.id)}>
          <div className={`flex min-w-0 items-center gap-1.5 py-[1px] ${indent ? "pl-4" : ""}`}>
            <List className="size-3.5 flex-shrink-0 stroke-[1.5]" />
            <span className="truncate text-11">{l.name}</span>
          </div>
        </SidebarNavItem>
      </Link>
    );
  };

  return (
    <div data-mawesi="module-tree" aria-label={t("tree.title")} className="mt-1 border-t border-subtle pt-1">
      {tree.folders.map((f) => {
        const isOpen = !!open[`${projectId}:${f.name}`] || f.lists.some((l) => pathname.includes(l.id));
        return (
          <div key={f.name}>
            <button type="button" className="w-full text-left" onClick={() => toggle(f.name)} aria-expanded={isOpen} data-mawesi="tree-folder">
              <SidebarNavItem isActive={false}>
                <div className="flex min-w-0 items-center gap-1.5 py-[1px]">
                  <ChevronRight className={`size-3 flex-shrink-0 transition-transform ${isOpen ? "rotate-90" : ""}`} />
                  {isOpen ? <FolderOpen className="size-3.5 flex-shrink-0 stroke-[1.5]" /> : <Folder className="size-3.5 flex-shrink-0 stroke-[1.5]" />}
                  <span className="truncate text-11 font-medium">{f.name}</span>
                  <span className="ml-auto text-11 text-tertiary">{f.lists.length}</span>
                </div>
              </SidebarNavItem>
            </button>
            {isOpen && f.lists.map((l) => listLink(l, true))}
          </div>
        );
      })}
      {tree.loose.map((l) => listLink(l, false))}
    </div>
  );
});
