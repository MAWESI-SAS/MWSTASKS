/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Ventana para crear, renombrar y mover carpetas y listas del árbol. Por detrás todo es un módulo de Plane
 * llamado "Carpeta / Lista": el usuario nunca escribe el separador.
 */
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { observer } from "mobx-react";
import { useNavigate } from "react-router";
import { useT } from "../i18n";
import { Button, Input, TOAST_TYPE, setToast, useModule } from "../plane";
import { MawesiModal } from "../ui/modal";
import { groupModules, isValidPart, moduleName } from "./group";
import type { TList } from "./group";

export type TTreeDialog =
  | { kind: "new-folder" }
  | { kind: "new-list"; folder: string }
  | { kind: "rename-folder"; folder: string }
  | { kind: "rename-list"; folder: string; list: TList }
  | { kind: "move-list"; folder: string; list: TList };

type Props = { dialog: TTreeDialog | null; onClose: () => void; workspaceSlug: string; projectId: string };

const NEW_FOLDER = "\u0000new";
const selectClass = "w-full rounded-md border border-subtle bg-surface-1 px-2 py-1.5 text-13";

export const TreeDialog = observer(function TreeDialog({ dialog, onClose, workspaceSlug, projectId }: Props) {
  const t = useT();
  const navigate = useNavigate();
  const { createModule, updateModuleDetails, getProjectModuleDetails, fetchModules } = useModule();
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");
  const [target, setTarget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!dialog) return;
    setFirst(dialog.kind === "rename-folder" ? dialog.folder : dialog.kind === "rename-list" ? dialog.list.name : "");
    setSecond("");
    setTarget(dialog.kind === "move-list" ? dialog.folder : "");
    setError(null);
  }, [dialog]);

  if (!dialog) return null;

  // Siempre el árbol actual del store (no el de cuando se abrió la ventana): otra acción pudo cambiarlo.
  const tree = groupModules(getProjectModuleDetails(projectId) ?? []);
  const folderNames = tree.folders.map((f) => f.name);
  const listsIn = (folder: string) => (folder ? (tree.folders.find((f) => f.name === folder)?.lists ?? []) : tree.loose);
  const listTaken = (folder: string, name: string, exceptId?: string) =>
    listsIn(folder).some((l) => l.id !== exceptId && l.name.toLowerCase() === name.trim().toLowerCase());
  const folderTaken = (name: string, except?: string) =>
    folderNames.some((f) => f !== except && f.toLowerCase() === name.trim().toLowerCase());

  const title = {
    "new-folder": t("tree.new_folder"),
    "new-list": t("tree.new_list"),
    "rename-folder": t("tree.rename_folder"),
    "rename-list": t("tree.rename_list"),
    "move-list": t("tree.move_title"),
  }[dialog.kind];

  /** Devuelve el error a mostrar o null si se puede guardar. */
  const check = (): string | null => {
    switch (dialog.kind) {
      case "new-folder":
        if (!isValidPart(first) || !isValidPart(second)) return t("tree.err_name");
        return folderTaken(first) ? t("tree.err_folder_exists") : null;
      case "new-list":
        if (!isValidPart(first)) return t("tree.err_name");
        return listTaken(dialog.folder, first) ? t("tree.err_list_exists") : null;
      case "rename-folder":
        if (!isValidPart(first)) return t("tree.err_name");
        return folderTaken(first, dialog.folder) ? t("tree.err_folder_exists") : null;
      case "rename-list":
        if (!isValidPart(first)) return t("tree.err_name");
        return listTaken(dialog.folder, first, dialog.list.id) ? t("tree.err_list_exists") : null;
      case "move-list": {
        if (target === NEW_FOLDER) {
          if (!isValidPart(first)) return t("tree.err_name");
          return folderTaken(first) ? t("tree.err_folder_exists") : null;
        }
        return listTaken(target, dialog.list.name, dialog.list.id) ? t("tree.err_list_exists") : null;
      }
    }
  };

  const open = (moduleId: string) => navigate(`/${workspaceSlug}/projects/${projectId}/modules/${moduleId}`);
  const rename = (id: string, name: string) => updateModuleDetails(workspaceSlug, projectId, id, { name });

  const save = async () => {
    switch (dialog.kind) {
      case "new-folder":
        return open((await createModule(workspaceSlug, projectId, { name: moduleName(first, second) })).id);
      case "new-list":
        return open((await createModule(workspaceSlug, projectId, { name: moduleName(dialog.folder, first) })).id);
      case "rename-folder": {
        // Las listas de la carpeta se leen del servidor: una lectura vieja en vuelo pudo pisar el store
        // (p. ej. una lista recién movida volvería a aparecer acá y se renombraría con la carpeta).
        await fetchModules(workspaceSlug, projectId);
        const lists = groupModules(getProjectModuleDetails(projectId) ?? []).folders.find((f) => f.name === dialog.folder)?.lists ?? [];
        // Una por vez: si una falla, las ya renombradas quedan bien y el resto sigue en la carpeta vieja.
        for (const l of lists) await rename(l.id, moduleName(first, l.name));
        return;
      }
      case "rename-list":
        return void (await rename(dialog.list.id, moduleName(dialog.folder, first)));
      case "move-list":
        return void (await rename(dialog.list.id, moduleName(target === NEW_FOLDER ? first : target, dialog.list.name)));
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const problem = check();
    if (problem) return setError(problem);
    setSaving(true);
    try {
      await save();
      onClose();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("tree.error") });
    } finally {
      setSaving(false);
    }
  };

  const nameField = (label: string, value: string, onChange: (v: string) => void, name: string, autoFocus = true) => (
    <label className="block space-y-1">
      <span className="text-13 text-secondary">{label}</span>
      <Input name={name} value={value} onChange={(e) => onChange(e.target.value)} className="w-full" autoFocus={autoFocus} maxLength={120} />
    </label>
  );

  return (
    <MawesiModal isOpen onClose={onClose}>
      <form onSubmit={submit} className="space-y-4 px-5 py-4" data-mawesi="tree-dialog">
        <h3 className="text-18 font-medium">{title}</h3>
        {dialog.kind === "new-folder" && (
          <>
            {nameField(t("tree.folder"), first, setFirst, "folder")}
            {nameField(t("tree.first_list"), second, setSecond, "list", false)}
          </>
        )}
        {dialog.kind === "new-list" && nameField(t("tree.list"), first, setFirst, "list")}
        {dialog.kind === "rename-folder" && nameField(t("tree.folder"), first, setFirst, "folder")}
        {dialog.kind === "rename-list" && nameField(t("tree.list"), first, setFirst, "list")}
        {dialog.kind === "move-list" && (
          <>
            <p className="text-13 text-secondary">{dialog.list.name}</p>
            <label className="block space-y-1">
              <span className="text-13 text-secondary">{t("tree.folder")}</span>
              <select name="target" value={target} onChange={(e) => setTarget(e.target.value)} className={selectClass}>
                {folderNames.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
                <option value="">{t("tree.no_folder")}</option>
                <option value={NEW_FOLDER}>{t("tree.move_new_folder")}</option>
              </select>
            </label>
            {target === NEW_FOLDER && nameField(t("tree.new_folder"), first, setFirst, "folder")}
          </>
        )}
        {error && (
          <p className="text-13 text-danger-primary" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="lg" onClick={onClose}>
            {t("tree.cancel")}
          </Button>
          <Button type="submit" variant="primary" size="lg" loading={saving} data-mawesi="tree-dialog-save">
            {saving ? t("tree.saving") : t("tree.save")}
          </Button>
        </div>
      </form>
    </MawesiModal>
  );
});
