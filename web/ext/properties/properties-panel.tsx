/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
import { Calendar, CircleDot, Hash, Link2, ListChecks, Shapes, ToggleLeft, Type, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useT } from "../i18n";
import { TOAST_TYPE, Tooltip, setToast, useIssueDetail } from "../plane";
import { typeService } from "../types/service";
import { useIssueType, useProjectTypes } from "../types/use-types";
import { useWorklogPermissions } from "../worklog/use-worklogs";
import { GhostSelect, PropertyEditor } from "./property-editor";
import { propertyService } from "./service";
import type { TProperty, TPropertyType, TValue } from "./service";

const ICONS: Record<TPropertyType, LucideIcon> = {
  text: Type, url: Link2, number: Hash, date: Calendar, checkbox: ToggleLeft, select: CircleDot, multi_select: ListChecks, member: UserRound,
};
import { useIssueValues, useProjectProperties } from "./use-properties";

/** Como SidebarPropertyListItem de Plane, pero el nombre ocupa una sola línea: si no entra se corta con "…" y el
 * nombre completo (y la descripción, si hay) sale al pasar el mouse. Así todas las filas tienen la misma altura. */
function FieldRow({ icon: Icon, name, description, children }: { icon: LucideIcon; name: string; description?: string; children: React.ReactNode }) {
  const [cut, setCut] = useState(false);
  const labelRef = useRef<HTMLSpanElement>(null);
  const help = description?.trim();
  useEffect(() => {
    const el = labelRef.current;
    if (!el) return;
    const measure = () => setCut(el.scrollWidth > el.clientWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [name]);
  return (
    <div className="flex items-start gap-2">
      <Tooltip
        tooltipContent={help ? `${name}: ${help}` : name}
        position="top-start"
        disabled={!cut && !help}
        renderByDefault={false}
      >
        <div className="flex h-7.5 w-30 min-w-0 shrink-0 items-center gap-1.5 text-body-xs-regular text-tertiary">
          <Icon className="size-4 shrink-0" />
          <span ref={labelRef} className="truncate">
            {name}
          </span>
        </div>
      </Tooltip>
      <div className="flex min-w-0 grow flex-nowrap items-center gap-1">{children}</div>
    </div>
  );
}

type Props = { workspaceSlug: string; projectId: string; issueId: string; disabled?: boolean };

export const PropertiesPanel = observer(function PropertiesPanel({ workspaceSlug, projectId, issueId, disabled }: Props) {
  const t = useT();
  const { canWrite } = useWorklogPermissions(workspaceSlug, projectId);
  const { properties } = useProjectProperties(workspaceSlug, projectId);
  const { types } = useProjectTypes(workspaceSlug, projectId);
  const { issueType, mutate: mutateType } = useIssueType(workspaceSlug, projectId, issueId);
  const { values, mutate } = useIssueValues(workspaceSlug, projectId, issueId);
  const { fetchActivities } = useIssueDetail();

  if (!canWrite || (properties.length === 0 && types.length === 0)) return null;

  const save = async (propertyId: string, value: TValue) => {
    try {
      const next = await propertyService.setValues(workspaceSlug, projectId, issueId, { [propertyId]: value });
      await mutate(next, { revalidate: false });
      fetchActivities(workspaceSlug, projectId, issueId).catch(() => undefined);
    } catch (e: unknown) {
      const msg = (e as { errors?: Record<string, string> })?.errors?.[propertyId];
      setToast({ type: TOAST_TYPE.ERROR, title: t("fields.value_error"), message: msg });
      await mutate();
    }
  };

  const changeType = async (typeId: string) => {
    try {
      await mutateType(await typeService.setOfIssue(workspaceSlug, projectId, issueId, typeId || null), { revalidate: false });
      fetchActivities(workspaceSlug, projectId, issueId).catch(() => undefined);
    } catch (e: unknown) {
      setToast({ type: TOAST_TYPE.ERROR, title: (e as { error?: string })?.error ?? t("worklog.error") });
    }
  };

  // Con tipo: solo sus campos, en su orden. Sin tipo: todos (como antes de existir los tipos).
  const byId = new Map(properties.map((p) => [p.id, p]));
  const shown = issueType?.property_ids ? issueType.property_ids.map((id) => byId.get(id)).filter((p): p is TProperty => !!p) : properties;
  const current = types.find((x) => x.id === issueType?.type_id);
  const auto = issueType?.source && issueType.source !== "issue" && current ? `${t("types.auto")}: ${current.name}` : t("types.auto");

  return (
    <div data-mawesi="properties-panel">
      <h5 className="text-body-xs-medium">{t("fields.title")}</h5>
      <div className={`mt-4 mb-2 space-y-2.5 ${disabled ? "opacity-60" : ""}`}>
        {types.length > 0 && (
          <div data-mawesi-field="__type" data-type={current?.name ?? ""} data-source={issueType?.source ?? ""}>
            <FieldRow icon={Shapes} name={t("types.field_label")} description={current?.description}>
              <GhostSelect value={issueType?.source === "issue" ? (issueType.type_id ?? "") : ""} disabled={disabled} onSave={changeType} testId="type">
                <option value="">{auto}</option>
                {types.map((ty) => (
                  <option key={ty.id} value={ty.id}>
                    {ty.name}
                  </option>
                ))}
              </GhostSelect>
            </FieldRow>
          </div>
        )}
        {shown.map((p) => (
          <div key={p.id} data-mawesi-field={p.name}>
            <FieldRow icon={ICONS[p.type]} name={p.name} description={p.description}>
              <PropertyEditor prop={p} value={values[p.id] ?? null} projectId={projectId} disabled={disabled} onSave={(v) => save(p.id, v)} />
            </FieldRow>
          </div>
        ))}
      </div>
    </div>
  );
});
