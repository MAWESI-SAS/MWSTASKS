/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { observer } from "mobx-react";
import { LockOpen } from "lucide-react";
import { useT } from "../i18n";
import { IssueActivityBlockComponent, useIssueDetail } from "../plane";

export const DEPENDENCY_FIELD = "mawesi_dependency";

type Props = { activityId: string; ends: "top" | "bottom" | undefined };

/** Fila del historial "se desbloqueó: terminó TQ-12" (backend dependencies.unblock). */
export const DependencyActivity = observer(function DependencyActivity({ activityId, ends }: Props) {
  const t = useT();
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  const a = getActivityById(activityId);
  if (!a) return null;
  return (
    <IssueActivityBlockComponent icon={<LockOpen className="h-3.5 w-3.5 text-secondary" aria-hidden="true" />} activityId={activityId} ends={ends}>
      <span data-mawesi="dependency-activity">
        {t("dep.unblocked_by")} {a.new_value}.
      </span>
    </IssueActivityBlockComponent>
  );
});
