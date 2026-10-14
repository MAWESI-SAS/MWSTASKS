/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { observer } from "mobx-react";
import { Clock } from "lucide-react";
import { useT } from "../i18n";
import { IssueActivityBlockComponent, useIssueDetail } from "../plane";
import { formatMinutes } from "./format";

export const WORKLOG_FIELD = "worklog";

type Props = { activityId: string; ends: "top" | "bottom" | undefined };

/** Fila del historial para field="worklog" (Plane devuelve null para campos que no conoce). */
export const WorklogActivity = observer(function WorklogActivity({ activityId, ends }: Props) {
  const t = useT();
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  const a = getActivityById(activityId);
  if (!a) return null;
  const mins = (v?: string | null) => (v ? formatMinutes(Number(v)) : "");
  const text =
    a.verb === "updated"
      ? `${t("activity.updated")} ${mins(a.old_value)} ${t("activity.to")} ${mins(a.new_value)}`
      : a.verb === "deleted"
        ? `${t("activity.deleted")} ${mins(a.old_value)}`
        : `${t("activity.created")} ${mins(a.new_value)}`;
  return (
    <IssueActivityBlockComponent icon={<Clock className="h-3.5 w-3.5 text-secondary" aria-hidden="true" />} activityId={activityId} ends={ends}>
      <span data-mawesi="worklog-activity">{text}.</span>
    </IssueActivityBlockComponent>
  );
});
