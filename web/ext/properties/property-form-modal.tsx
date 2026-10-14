/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Plus, X } from "lucide-react";
import { useT } from "../i18n";
import type { TKey } from "../i18n";
import { Button, Input, TOAST_TYPE, setToast } from "../plane";
import { MawesiModal } from "../ui/modal";
import { OPTION_TYPES, PROPERTY_TYPES, propertyService } from "./service";
import type { TProperty, TPropertyOption, TPropertyType } from "./service";

type Props = { isOpen: boolean; onClose: () => void; onSaved: () => Promise<unknown>; workspaceSlug: string; projectId: string; prop?: TProperty };

export function PropertyFormModal({ isOpen, onClose, onSaved, workspaceSlug, projectId, prop }: Props) {
  const t = useT();
  const [name, setName] = useState("");
  const [type, setType] = useState<TPropertyType>("text");
  const [options, setOptions] = useState<TPropertyOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setName(prop?.name ?? "");
    setType(prop?.type ?? "text");
    setOptions(prop?.options.map((o) => ({ id: o.id, name: o.name })) ?? []);
    setError(null);
  }, [isOpen, prop]);

  const withOptions = OPTION_TYPES.includes(type);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const payload = {
      name: name.trim(),
      ...(prop ? {} : { type }),
      ...(withOptions ? { options: options.filter((o) => o.name.trim()).map((o, i) => ({ ...o, name: o.name.trim(), sort_order: (i + 1) * 1000 })) } : {}),
    };
    if (!payload.name) return setError(t("fields.name"));
    setSaving(true);
    try {
      if (prop) await propertyService.update(workspaceSlug, projectId, prop.id, payload);
      else await propertyService.create(workspaceSlug, projectId, payload);
      await onSaved();
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("fields.saved") });
      onClose();
    } catch (err: unknown) {
      const data = err as { error?: string; name?: string[]; type?: string[] };
      setError(data?.error ?? data?.name?.[0] ?? data?.type?.[0] ?? t("worklog.error"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <MawesiModal isOpen={isOpen} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4 px-5 py-4" data-mawesi="property-modal">
        <h3 className="text-18 font-medium">{prop ? t("fields.edit") : t("fields.add")}</h3>
        <label className="block space-y-1">
          <span className="text-13 text-secondary">{t("fields.name")}</span>
          <Input name="name" value={name} onChange={(e) => setName(e.target.value)} className="w-full" autoFocus maxLength={120} />
        </label>
        <label className="block space-y-1">
          <span className="text-13 text-secondary">{t("fields.type")}</span>
          <select
            name="type"
            value={type}
            disabled={!!prop}
            onChange={(e) => setType(e.target.value as TPropertyType)}
            className="w-full rounded-md border border-subtle bg-surface-1 px-2 py-1.5 text-13 disabled:opacity-60"
          >
            {PROPERTY_TYPES.map((pt) => (
              <option key={pt} value={pt}>
                {t(`fields.type.${pt}` as TKey)}
              </option>
            ))}
          </select>
        </label>
        {withOptions && (
          <div className="space-y-1">
            <span className="text-13 text-secondary">{t("fields.options")}</span>
            {options.map((o, i) => (
              <div key={o.id ?? `new-${i}`} className="flex items-center gap-2">
                <Input
                  name={`option-${i}`}
                  value={o.name}
                  placeholder={t("fields.option_placeholder")}
                  onChange={(e) => setOptions(options.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
                  className="w-full"
                />
                <button type="button" aria-label="Quitar" onClick={() => setOptions(options.filter((_, j) => j !== i))} className="rounded p-1 hover:bg-layer-1">
                  <X className="size-3.5" />
                </button>
              </div>
            ))}
            <button type="button" onClick={() => setOptions([...options, { name: "" }])} className="flex items-center gap-1 text-13 text-secondary hover:text-primary" data-mawesi="add-option">
              <Plus className="size-3.5" />
              {t("fields.add_option")}
            </button>
          </div>
        )}
        {error && <p className="text-13 text-danger-primary" role="alert">{error}</p>}
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
