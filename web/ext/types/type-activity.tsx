/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { observer } from "mobx-react";
import { Shapes } from "lucide-react";
import { useT } from "../i18n";
import { IssueActivityBlockComponent, useIssueDetail } from "../plane";

export const TYPE_FIELD = "mawesi_type";

type Props = { activityId: string; ends: "top" | "bottom" | undefined };

/** Fila del historial para field="mawesi_type" (cambio del tipo de tarea; ver backend types.py). */
export const TypeActivity = observer(function TypeActivity({ activityId, ends }: Props) {
  const t = useT();
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  const a = getActivityById(activityId);
  if (!a) return null;
  const text = a.new_value ? `${t("activity.type_set")} ${a.new_value}` : t("activity.type_removed");
  return (
    <IssueActivityBlockComponent icon={<Shapes className="h-3.5 w-3.5 text-secondary" aria-hidden="true" />} activityId={activityId} ends={ends}>
      <span data-mawesi="type-activity">{text}.</span>
    </IssueActivityBlockComponent>
  );
});
