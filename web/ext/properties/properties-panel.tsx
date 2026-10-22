/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
import { Calendar, CircleDot, Hash, Link2, ListChecks, ToggleLeft, Type, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useT } from "../i18n";
import { TOAST_TYPE, Tooltip, setToast, useIssueDetail } from "../plane";
import { useWorklogPermissions } from "../worklog/use-worklogs";
import { PropertyEditor } from "./property-editor";
import { propertyService } from "./service";
import type { TProperty, TPropertyType, TValue } from "./service";

const ICONS: Record<TPropertyType, LucideIcon> = {
  text: Type, url: Link2, number: Hash, date: Calendar, checkbox: ToggleLeft, select: CircleDot, multi_select: ListChecks, member: UserRound,
};
import { useIssueValues, useProjectProperties } from "./use-properties";

/** Como SidebarPropertyListItem de Plane, pero el nombre ocupa una sola línea: si no entra se corta con "…" y el
 * nombre completo (y la descripción, si hay) sale al pasar el mouse. Así todas las filas tienen la misma altura. */
function FieldRow({ prop, children }: { prop: TProperty; children: React.ReactNode }) {
  const Icon = ICONS[prop.type];
  const [cut, setCut] = useState(false);
  const labelRef = useRef<HTMLSpanElement>(null);
  const help = prop.description?.trim();
  useEffect(() => {
    const el = labelRef.current;
    if (!el) return;
    const measure = () => setCut(el.scrollWidth > el.clientWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [prop.name]);
  return (
    <div className="flex items-start gap-2">
      <Tooltip
        tooltipContent={help ? `${prop.name}: ${help}` : prop.name}
        position="top-start"
        disabled={!cut && !help}
        renderByDefault={false}
      >
        <div className="flex h-7.5 w-30 min-w-0 shrink-0 items-center gap-1.5 text-body-xs-regular text-tertiary">
          <Icon className="size-4 shrink-0" />
          <span ref={labelRef} className="truncate">
            {prop.name}
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
  const { values, mutate } = useIssueValues(workspaceSlug, projectId, issueId);
  const { fetchActivities } = useIssueDetail();

  if (!canWrite || properties.length === 0) return null;

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

  return (
    <div data-mawesi="properties-panel">
      <h5 className="text-body-xs-medium">{t("fields.title")}</h5>
      <div className={`mt-4 mb-2 space-y-2.5 ${disabled ? "opacity-60" : ""}`}>
        {properties.map((p) => (
          <div key={p.id} data-mawesi-field={p.name}>
            <FieldRow prop={p}>
              <PropertyEditor prop={p} value={values[p.id] ?? null} projectId={projectId} disabled={disabled} onSave={(v) => save(p.id, v)} />
            </FieldRow>
          </div>
        ))}
      </div>
    </div>
  );
});
