/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { observer } from "mobx-react";
import { Calendar, CircleDot, Hash, Link2, ListChecks, ToggleLeft, Type, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useT } from "../i18n";
import { SidebarPropertyListItem, TOAST_TYPE, setToast, useIssueDetail } from "../plane";
import { useWorklogPermissions } from "../worklog/use-worklogs";
import { PropertyEditor } from "./property-editor";
import { propertyService } from "./service";
import type { TPropertyType, TValue } from "./service";

const ICONS: Record<TPropertyType, LucideIcon> = {
  text: Type, url: Link2, number: Hash, date: Calendar, checkbox: ToggleLeft, select: CircleDot, multi_select: ListChecks, member: UserRound,
};
import { useIssueValues, useProjectProperties } from "./use-properties";

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
            <SidebarPropertyListItem icon={ICONS[p.type]} label={p.name} childrenClassName="min-w-0 flex-nowrap">
              <PropertyEditor prop={p} value={values[p.id] ?? null} projectId={projectId} disabled={disabled} onSave={(v) => save(p.id, v)} />
            </SidebarPropertyListItem>
          </div>
        ))}
      </div>
    </div>
  );
});
