/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Historial: nuestras filas (worklog, estimado, dependencias, campos propios y tipo) las pintamos nosotros; el resto, Plane.
 */
import type { ComponentProps } from "react";
import { observer } from "mobx-react";
import { IssueActivityItem as Upstream } from "@upstream/components/issues/issue-detail/issue-activity/activity/activity-list";
import { DEPENDENCY_FIELD, DependencyActivity } from "../../dependencies/dependency-activity";
import { ESTIMATE_FIELD, EstimateActivity } from "../../estimates/estimate-activity";
import { useIssueDetail } from "../../plane";
import { PROPERTY_FIELD, PropertyActivity } from "../../properties/property-activity";
import { TYPE_FIELD, TypeActivity } from "../../types/type-activity";
import { WORKLOG_FIELD, WorklogActivity } from "../../worklog/worklog-activity";

export const IssueActivityItem = observer(function IssueActivityItem(props: ComponentProps<typeof Upstream>) {
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  const field = getActivityById(props.activityId)?.field;
  if (field === WORKLOG_FIELD) return <WorklogActivity activityId={props.activityId} ends={props.ends} />;
  if (field === DEPENDENCY_FIELD) return <DependencyActivity activityId={props.activityId} ends={props.ends} />;
  if (field === ESTIMATE_FIELD) return <EstimateActivity activityId={props.activityId} ends={props.ends} />;
  if (field === PROPERTY_FIELD) return <PropertyActivity activityId={props.activityId} ends={props.ends} />;
  if (field === TYPE_FIELD) return <TypeActivity activityId={props.activityId} ends={props.ends} />;
  return <Upstream {...props} />;
});
