/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Editor de un valor según el tipo de campo, con el estilo "transparente" de las propiedades de Plane
 * (sin borde, fondo al pasar el mouse, h-7.5, text-body-xs-regular). Llama a onSave solo si el valor cambia.
 */
import { useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
import { ChevronDown, Pencil } from "lucide-react";
import { useT } from "../i18n";
import { useMember } from "../plane";
import { Toggle } from "../ui/toggle";
import { LinkChip } from "./link-chip";
import type { TProperty, TValue } from "./service";

type Props = { prop: TProperty; value: TValue; projectId: string; disabled?: boolean; onSave: (v: TValue) => void };

/** Mismo aspecto que los botones "transparent-with-text" de las propiedades de Plane. */
export const GHOST =
  "h-7.5 w-full rounded-sm border-0 bg-transparent px-2 text-left text-body-xs-regular text-primary outline-none " +
  "placeholder:text-placeholder hover:bg-layer-transparent-hover focus:bg-layer-transparent-hover disabled:cursor-not-allowed";

/** Texto, URL, número y fecha: se guarda al salir del campo o con Enter. */
function TextLike({ prop, value, disabled, onSave, autoFocus, onDone }: Props & { autoFocus?: boolean; onDone?: () => void }) {
  const t = useT();
  const [draft, setDraft] = useState(value == null ? "" : String(value));
  const cancelled = useRef(false);
  useEffect(() => setDraft(value == null ? "" : String(value)), [value]);
  const commit = () => {
    if (cancelled.current) {
      cancelled.current = false;
      onDone?.();
      return;
    }
    const next = draft.trim() === "" ? null : draft.trim();
    if (String(next ?? "") !== String(value ?? "")) onSave(next);
    onDone?.();
  };
  const type = prop.type === "number" ? "number" : prop.type === "date" ? "date" : prop.type === "url" ? "url" : "text";
  return (
    <input
      type={type}
      value={draft}
      disabled={disabled}
      autoFocus={autoFocus}
      placeholder={t("fields.empty_value")}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        if (e.key === "Escape") {
          cancelled.current = true;
          e.currentTarget.blur(); // commit ve la marca, no guarda y la limpia
          setDraft(value == null ? "" : String(value));
        }
      }}
      className={`${GHOST} ${type === "date" && !draft ? "text-placeholder" : ""}`}
      data-mawesi-input={prop.type}
    />
  );
}

/** Link: se ve como ClickUp (ícono del sitio + nombre, abre en otra pestaña); el lápiz lo edita. */
function UrlField(props: Props) {
  const t = useT();
  const [editing, setEditing] = useState(false);
  const { value, disabled } = props;
  if (editing || typeof value !== "string" || !value) return <TextLike {...props} autoFocus={editing} onDone={() => setEditing(false)} />;
  return (
    <div className="group flex h-7.5 w-full min-w-0 items-center gap-1 rounded-sm px-2 hover:bg-layer-transparent-hover">
      <LinkChip url={value} />
      {!disabled && (
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="ml-auto hidden shrink-0 rounded-sm p-0.5 text-tertiary group-hover:inline-flex hover:text-primary"
          aria-label={t("fields.edit_link")}
          data-mawesi-input="url-edit"
        >
          <Pencil className="size-3.5" />
        </button>
      )}
    </div>
  );
}

/** Lista desplegable nativa con aspecto transparente y flecha al pasar el mouse (como Plane). */
function GhostSelect({ value, disabled, onSave, children, testId }: { value: string; disabled?: boolean; onSave: (v: string) => void; children: React.ReactNode; testId: string }) {
  return (
    <div className="group relative w-full">
      <select
        className={`${GHOST} cursor-pointer appearance-none pr-6 ${value ? "" : "text-placeholder"}`}
        disabled={disabled}
        value={value}
        onChange={(e) => onSave(e.target.value)}
        data-mawesi-input={testId}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute top-1/2 right-2 hidden size-3.5 -translate-y-1/2 text-tertiary group-hover:inline" />
    </div>
  );
}

/** Selección múltiple: botón transparente con las opciones elegidas y lista con casillas. */
function MultiSelect({ prop, value, disabled, onSave }: Props) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = Array.isArray(value) ? value : [];
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  const toggle = (id: string) => {
    const next = selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id];
    onSave(next.length ? next : null);
  };
  const names = prop.options.filter((o) => o.id && selected.includes(o.id)).map((o) => o.name);
  return (
    <div className="group relative w-full" ref={ref}>
      <button type="button" disabled={disabled} onClick={() => setOpen(!open)} className={`${GHOST} flex items-center justify-between gap-1`} data-mawesi-input="multi_select">
        <span className={`truncate ${names.length ? "" : "text-placeholder"}`}>{names.length ? names.join(", ") : t("fields.empty_value")}</span>
        <ChevronDown className="hidden size-3.5 shrink-0 text-tertiary group-hover:inline" />
      </button>
      {open && (
        <div className="absolute z-20 mt-1 max-h-60 w-full overflow-y-auto rounded-md border border-subtle bg-surface-1 p-1 shadow-raised-200">
          {prop.options.map((o) => (
            <label key={o.id} className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1 text-body-xs-regular hover:bg-layer-transparent-hover">
              <input type="checkbox" checked={!!o.id && selected.includes(o.id)} onChange={() => o.id && toggle(o.id)} />
              {o.name}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

const MemberSelect = observer(function MemberSelect({ value, projectId, disabled, onSave }: Props) {
  const t = useT();
  const {
    getUserDetails,
    project: { getProjectMemberIds },
  } = useMember();
  const ids = getProjectMemberIds(projectId, false) ?? [];
  return (
    <GhostSelect value={typeof value === "string" ? value : ""} disabled={disabled} onSave={(v) => onSave(v || null)} testId="member">
      <option value="">{t("fields.empty_value")}</option>
      {ids.map((id) => (
        <option key={id} value={id}>
          {getUserDetails(id)?.display_name ?? id}
        </option>
      ))}
    </GhostSelect>
  );
});

export function PropertyEditor(props: Props) {
  const t = useT();
  const { prop, value, disabled, onSave } = props;
  switch (prop.type) {
    case "checkbox":
      return (
        <div className="flex h-7.5 items-center px-2">
          <Toggle value={value === true} onChange={(v) => onSave(v)} disabled={disabled} label={prop.name} />
        </div>
      );
    case "select":
      return (
        <GhostSelect value={typeof value === "string" ? value : ""} disabled={disabled} onSave={(v) => onSave(v || null)} testId="select">
          <option value="">{t("fields.empty_value")}</option>
          {prop.options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </GhostSelect>
      );
    case "multi_select":
      return <MultiSelect {...props} />;
    case "member":
      return <MemberSelect {...props} />;
    case "url":
      return <UrlField {...props} />;
    default:
      return <TextLike {...props} />;
  }
}
