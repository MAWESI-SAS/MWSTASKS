/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Árbol "Carpeta > Lista" debajo de cada proyecto en el menú lateral (como la jerarquía de ClickUp).
 * Es la ÚNICA forma de ver y ordenar las listas: el ítem "Módulos" de Plane se oculta (ver project-navigation).
 * Cada lista abre su módulo. Desde los menús "⋯" se crean, renombran, mueven y borran carpetas y listas.
 * Lo abierto/cerrado se recuerda por navegador.
 */
import { useState } from "react";
import type { ReactNode } from "react";
import { observer } from "mobx-react";
import { Link, useLocation, useNavigate } from "react-router";
import useSWR from "swr";
import { ChevronRight, Folder, FolderOpen, FolderInput, List, MoreHorizontal, Pencil, Plus, Trash2 } from "lucide-react";
import { useT } from "../i18n";
import { CustomMenu, EUserPermissions, IconButton, SidebarNavItem, TOAST_TYPE, setToast, useModule, useProject, useUser, useUserPermissions } from "../plane";
import { MawesiConfirm } from "../ui/confirm";
import { groupModules } from "./group";
import type { TList } from "./group";
import { TreeDialog } from "./tree-dialog";
import type { TTreeDialog } from "./tree-dialog";

type Props = { workspaceSlug: string; projectId: string };
type TDelete = { folder: string; list?: TList; lists: TList[] };

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

type TAction = { key: string; label: string; icon: typeof Plus; onClick: () => void; danger?: boolean };

/** Botón "⋯" que aparece al pasar el mouse por la fila (mismo patrón que el menú de proyectos de Plane). */
function RowMenu({ actions, label, testId, trigger = MoreHorizontal }: { actions: TAction[]; label: string; testId: string; trigger?: typeof Plus }) {
  const [active, setActive] = useState(false);
  if (actions.length === 0) return null;
  return (
    <CustomMenu
      customButton={
        <IconButton variant="ghost" size="sm" icon={trigger} onClick={() => setActive(!active)} className="text-placeholder" data-mawesi={testId} />
      }
      className={`flex-shrink-0 ${active ? "opacity-100" : "pointer-events-none opacity-0 group-hover/tree-row:pointer-events-auto group-hover/tree-row:opacity-100"}`}
      customButtonClassName="grid place-items-center"
      placement="bottom-start"
      ariaLabel={label}
      useCaptureForOutsideClick
      closeOnSelect
      onMenuClose={() => setActive(false)}
    >
      {actions.map((a) => (
        <CustomMenu.MenuItem key={a.key} onClick={a.onClick}>
          <span className={`flex items-center gap-2 ${a.danger ? "text-danger-primary" : ""}`} data-mawesi={`tree-action-${a.key}`}>
            <a.icon className="size-3.5" />
            {a.label}
          </span>
        </CustomMenu.MenuItem>
      ))}
    </CustomMenu>
  );
}

const Row = ({ children, isActive = false }: { children: ReactNode; isActive?: boolean }) => (
  <div className="group/tree-row">
    <SidebarNavItem isActive={isActive} className="!py-0">
      {children}
    </SidebarNavItem>
  </div>
);

export const ModuleTree = observer(function ModuleTree({ workspaceSlug, projectId }: Props) {
  const t = useT();
  const navigate = useNavigate();
  const moduleStore = useModule();
  const { getPartialProjectById } = useProject();
  const { data: currentUser } = useUser();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const { pathname } = useLocation();
  const [open, setOpen] = useState<Record<string, boolean>>(readOpen);
  const [dialog, setDialog] = useState<TTreeDialog | null>(null);
  const [toDelete, setToDelete] = useState<TDelete | null>(null);
  const [deleting, setDeleting] = useState(false);
  // Plane solo carga los módulos del proyecto abierto: una llamada trae los de todo el workspace.
  useSWR(workspaceSlug ? ["mawesi-ws-modules", workspaceSlug] : null, () => moduleStore.fetchWorkspaceModules(workspaceSlug), {
    revalidateOnFocus: false,
  });
  const project = getPartialProjectById(projectId);
  const modules = moduleStore.getProjectModuleDetails(projectId) ?? [];
  // Mismos permisos que la API de módulos de Plane: crear/editar admin y miembro; borrar admin o quien la creó.
  const role = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId);
  const isAdmin = role === EUserPermissions.ADMIN;
  const canEdit = isAdmin || role === EUserPermissions.MEMBER;
  if (!project?.module_view || (modules.length === 0 && !canEdit)) return null;
  const tree = groupModules(modules);

  const toggle = (folder: string) => {
    const k = `${projectId}:${folder}`;
    const next = { ...open, [k]: !open[k] };
    setOpen(next);
    writeOpen(next);
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    setDeleting(true);
    const ids = (toDelete.list ? [toDelete.list] : toDelete.lists).map((l) => l.id);
    try {
      for (const id of ids) await moduleStore.deleteModule(workspaceSlug, projectId, id);
      if (ids.some((id) => pathname.includes(id))) navigate(`/${workspaceSlug}/projects/${projectId}/issues`);
      setToDelete(null);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("tree.error") });
    } finally {
      setDeleting(false);
    }
  };

  const listRow = (l: TList, folder: string) => {
    const canDelete = isAdmin || (!!currentUser?.id && l.created_by === currentUser.id);
    const actions: TAction[] = canEdit
      ? [
          { key: "rename", label: t("tree.rename"), icon: Pencil, onClick: () => setDialog({ kind: "rename-list", folder, list: l }) },
          { key: "move", label: t("tree.move"), icon: FolderInput, onClick: () => setDialog({ kind: "move-list", folder, list: l }) },
          ...(canDelete ? [{ key: "delete", label: t("tree.delete"), icon: Trash2, danger: true, onClick: () => setToDelete({ folder, list: l, lists: [] }) }] : []),
        ]
      : [];
    return (
      <Row key={l.id} isActive={pathname.includes(l.id)}>
        <Link
          to={`/${workspaceSlug}/projects/${projectId}/modules/${l.id}`}
          title={l.name}
          data-mawesi="tree-list"
          className={`flex min-w-0 flex-1 items-center gap-1.5 py-1 ${folder ? "pl-4" : ""}`}
        >
          <List className="size-3.5 flex-shrink-0 stroke-[1.5]" />
          <span className="truncate text-11">{l.name}</span>
        </Link>
        <RowMenu actions={actions} label={t("tree.actions")} testId="tree-list-menu" />
      </Row>
    );
  };

  return (
    <div data-mawesi="module-tree" aria-label={t("tree.title")} className="mt-1 border-t border-subtle pt-1">
      <Row>
        <span className="flex-1 py-1 text-11 font-medium text-tertiary">{t("tree.title")}</span>
        <RowMenu
          label={t("tree.actions")}
          testId="tree-add-menu"
          trigger={Plus}
          actions={
            canEdit
              ? [
                  { key: "new-folder", label: t("tree.new_folder"), icon: Folder, onClick: () => setDialog({ kind: "new-folder" }) },
                  { key: "new-list", label: t("tree.new_list"), icon: List, onClick: () => setDialog({ kind: "new-list", folder: "" }) },
                ]
              : []
          }
        />
      </Row>
      {tree.folders.map((f) => {
        const isOpen = !!open[`${projectId}:${f.name}`] || f.lists.some((l) => pathname.includes(l.id));
        const actions: TAction[] = canEdit
          ? [
              { key: "new-list", label: t("tree.new_list"), icon: Plus, onClick: () => setDialog({ kind: "new-list", folder: f.name }) },
              { key: "rename", label: t("tree.rename"), icon: Pencil, onClick: () => setDialog({ kind: "rename-folder", folder: f.name }) },
              ...(isAdmin ? [{ key: "delete", label: t("tree.delete"), icon: Trash2, danger: true, onClick: () => setToDelete({ folder: f.name, lists: f.lists }) }] : []),
            ]
          : [];
        return (
          <div key={f.name}>
            <Row>
              <button
                type="button"
                className="flex min-w-0 flex-1 items-center gap-1.5 py-1 text-left"
                onClick={() => toggle(f.name)}
                aria-expanded={isOpen}
                data-mawesi="tree-folder"
              >
                <ChevronRight className={`size-3 flex-shrink-0 transition-transform ${isOpen ? "rotate-90" : ""}`} />
                {isOpen ? <FolderOpen className="size-3.5 flex-shrink-0 stroke-[1.5]" /> : <Folder className="size-3.5 flex-shrink-0 stroke-[1.5]" />}
                <span className="truncate text-11 font-medium">{f.name}</span>
                <span className="ml-auto text-11 text-tertiary">{f.lists.length}</span>
              </button>
              <RowMenu actions={actions} label={t("tree.actions")} testId="tree-folder-menu" />
            </Row>
            {isOpen && f.lists.map((l) => listRow(l, f.name))}
          </div>
        );
      })}
      {tree.loose.map((l) => listRow(l, ""))}
      <TreeDialog dialog={dialog} onClose={() => setDialog(null)} tree={tree} workspaceSlug={workspaceSlug} projectId={projectId} />
      <MawesiConfirm
        isOpen={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={confirmDelete}
        title={toDelete?.list ? t("tree.delete_list_title") : t("tree.delete_folder_title")}
        body={
          toDelete?.list
            ? t("tree.delete_list_body").replace("{name}", toDelete.list.name)
            : t("tree.delete_folder_body").replace("{name}", toDelete?.folder ?? "").replace("{n}", String(toDelete?.lists.length ?? 0))
        }
        confirmText={t("tree.delete")}
        confirmingText={t("tree.deleting")}
        cancelText={t("tree.cancel")}
        isSubmitting={deleting}
      />
    </div>
  );
});
