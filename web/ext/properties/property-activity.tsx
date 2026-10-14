/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { observer } from "mobx-react";
import { ListChecks } from "lucide-react";
import { useT } from "../i18n";
import { IssueActivityBlockComponent, useIssueDetail } from "../plane";

export const PROPERTY_FIELD = "mawesi_property";

type Props = { activityId: string; ends: "top" | "bottom" | undefined };

export const PropertyActivity = observer(function PropertyActivity({ activityId, ends }: Props) {
  const t = useT();
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  const a = getActivityById(activityId);
  if (!a) return null;
  const show = (v?: string | null) => (v === "true" ? t("fields.yes") : v === "false" ? t("fields.no") : (v ?? ""));
  const field = a.comment ?? "";
  const text = !a.new_value
    ? `${t("activity.prop_removed")} ${field}`
    : !a.old_value
      ? `${t("activity.prop_set")} ${field} ${t("activity.prop_in")} ${show(a.new_value)}`
      : `${t("activity.prop_changed")} ${field} ${t("activity.prop_from")} ${show(a.old_value)} ${t("activity.prop_in")} ${show(a.new_value)}`;
  return (
    <IssueActivityBlockComponent icon={<ListChecks className="h-3.5 w-3.5 text-secondary" aria-hidden="true" />} activityId={activityId} ends={ends}>
      <span data-mawesi="property-activity">{text}.</span>
    </IssueActivityBlockComponent>
  );
});
