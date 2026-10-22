/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Crear o editar un tipo de tarea: nombre, color, descripción, si es el del proyecto, qué campos muestra y qué listas
 * lo usan (una lista tiene un solo tipo: elegirla acá la saca de otro).
 */
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useT } from "../i18n";
import { Button, Input, TOAST_TYPE, TextArea, setToast } from "../plane";
import type { TProperty } from "../properties/service";
import { MODAL_WIDTH, MawesiModal } from "../ui/modal";
import { TYPE_COLORS, typeService } from "./service";
import type { TTypeColor, TWorkItemType } from "./service";

type TList = { id: string; name: string };
type Props = {
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => Promise<unknown>;
  workspaceSlug: string;
  projectId: string;
  type?: TWorkItemType;
  types: TWorkItemType[];
  properties: TProperty[];
  folders: Array<{ name: string; lists: TList[] }>;
};

const toggle = (list: string[], id: string) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

export function TypeFormModal({ isOpen, onClose, onSaved, workspaceSlug, projectId, type, types, properties, folders }: Props) {
  const t = useT();
  const [name, setName] = useState("");
  const [color, setColor] = useState<TTypeColor>("gray");
  const [description, setDescription] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [fields, setFields] = useState<string[]>([]);
  const [lists, setLists] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setName(type?.name ?? "");
    setColor(type?.color ?? "gray");
    setDescription(type?.description ?? "");
    setIsDefault(type?.is_default ?? false);
    setFields(type?.property_ids ?? []);
    setLists(type?.module_ids ?? []);
    setError(null);
  }, [isOpen, type]);

  const ownerOf = (listId: string) => types.find((x) => x.id !== type?.id && x.module_ids.includes(listId));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return setError(t("types.name"));
    // Los campos van en el orden del proyecto (el mismo del panel).
    const ordered = properties.filter((p) => fields.includes(p.id)).map((p) => p.id);
    const payload = { name: name.trim(), color, description: description.trim(), is_default: isDefault, property_ids: ordered, module_ids: lists };
    setSaving(true);
    try {
      if (type) await typeService.update(workspaceSlug, projectId, type.id, payload);
      else await typeService.create(workspaceSlug, projectId, payload);
      await onSaved();
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("types.saved") });
      onClose();
    } catch (err: unknown) {
      setError((err as { error?: string })?.error ?? t("worklog.error"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <MawesiModal isOpen={isOpen} onClose={onClose} width={MODAL_WIDTH.LG}>
      <form onSubmit={submit} className="space-y-4 px-5 py-4" data-mawesi="type-modal">
        <h3 className="text-18 font-medium">{type ? t("types.edit") : t("types.add")}</h3>
        <label className="block space-y-1">
          <span className="text-13 text-secondary">{t("types.name")}</span>
          <Input name="name" value={name} onChange={(e) => setName(e.target.value)} className="w-full" autoFocus maxLength={80} />
        </label>
        <div className="space-y-1">
          <span className="text-13 text-secondary">{t("types.color")}</span>
          <div className="flex flex-wrap gap-2">
            {(Object.keys(TYPE_COLORS) as TTypeColor[]).map((c) => (
              <button
                key={c}
                type="button"
                aria-label={c}
                aria-pressed={color === c}
                onClick={() => setColor(c)}
                className={`size-6 rounded-full border-2 ${color === c ? "border-primary" : "border-transparent"}`}
                style={{ backgroundColor: TYPE_COLORS[c] }}
                data-mawesi={`type-color-${c}`}
              />
            ))}
          </div>
        </div>
        <label className="block space-y-1">
          <span className="text-13 text-secondary">{t("types.description")}</span>
          <TextArea name="description" value={description} onChange={(e) => setDescription(e.target.value)} className="min-h-16 w-full" maxLength={500} />
        </label>
        <label className="flex items-center gap-2 text-13">
          <input type="checkbox" name="is_default" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
          {t("types.is_default")}
        </label>

        <fieldset className="space-y-1" data-mawesi="type-fields">
          <legend className="text-13 text-secondary">{t("types.fields")}</legend>
          <p className="text-11 text-tertiary">{t("types.fields_help")}</p>
          <div className="max-h-48 space-y-0.5 overflow-y-auto rounded-md border border-subtle p-2">
            {properties.length === 0 && <p className="text-13 text-tertiary">{t("fields.none")}</p>}
            {properties.map((p) => (
              <label key={p.id} className="flex cursor-pointer items-center gap-2 rounded-sm px-1 py-0.5 text-13 hover:bg-layer-transparent-hover">
                <input type="checkbox" checked={fields.includes(p.id)} onChange={() => setFields(toggle(fields, p.id))} data-mawesi-field={p.name} />
                <span className="truncate">{p.name}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="space-y-1" data-mawesi="type-lists">
          <legend className="text-13 text-secondary">{t("types.lists")}</legend>
          <p className="text-11 text-tertiary">{t("types.lists_help")}</p>
          <div className="max-h-48 space-y-2 overflow-y-auto rounded-md border border-subtle p-2">
            {folders.length === 0 && <p className="text-13 text-tertiary">{t("types.no_lists")}</p>}
            {folders.map((f) => (
              <div key={f.name}>
                {f.name && <p className="px-1 text-11 font-medium text-tertiary">{f.name}</p>}
                {f.lists.map((l) => {
                  const other = ownerOf(l.id);
                  return (
                    <label key={l.id} className="flex cursor-pointer items-center gap-2 rounded-sm px-1 py-0.5 text-13 hover:bg-layer-transparent-hover">
                      <input type="checkbox" checked={lists.includes(l.id)} onChange={() => setLists(toggle(lists, l.id))} data-mawesi-list={l.name} />
                      <span className="truncate">{l.name}</span>
                      {other && !lists.includes(l.id) && <span className="ml-auto shrink-0 text-11 text-tertiary">{other.name}</span>}
                    </label>
                  );
                })}
              </div>
            ))}
          </div>
        </fieldset>

        {error && (
          <p className="text-13 text-danger-primary" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="lg" onClick={onClose}>
            {t("worklog.cancel")}
          </Button>
          <Button type="submit" variant="primary" size="lg" loading={saving}>
            {saving ? t("worklog.saving") : t("worklog.save")}
          </Button>
        </div>
      </form>
    </MawesiModal>
  );
}
