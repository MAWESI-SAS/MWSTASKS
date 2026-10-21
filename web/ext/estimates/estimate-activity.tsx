/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { observer } from "mobx-react";
import { Hourglass } from "lucide-react";
import { useT } from "../i18n";
import { IssueActivityBlockComponent, useIssueDetail } from "../plane";
import { formatMinutes } from "../worklog/format";

export const ESTIMATE_FIELD = "estimate_hours";

type Props = { activityId: string; ends: "top" | "bottom" | undefined };

/** Fila del historial para field="estimate_hours" (cambio del estimado en horas; ver backend estimates.py). */
export const EstimateActivity = observer(function EstimateActivity({ activityId, ends }: Props) {
  const t = useT();
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  const a = getActivityById(activityId);
  if (!a) return null;
  const text = a.new_value
    ? `${t("activity.estimate_set")} ${formatMinutes(Number(a.new_value))}`
    : t("activity.estimate_removed");
  return (
    <IssueActivityBlockComponent icon={<Hourglass className="h-3.5 w-3.5 text-secondary" aria-hidden="true" />} activityId={activityId} ends={ends}>
      <span data-mawesi="estimate-activity">{text}.</span>
    </IssueActivityBlockComponent>
  );
});
