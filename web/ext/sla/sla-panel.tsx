/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Panel "Tiempo y SLA" del detalle de la tarea: plazo (si la tarea tiene SLA) y tiempo en cada estado.
 * El tiempo por estado sale del historial de Plane: cuenta desde que la tarea está en MWSTASKS.
 */
import { observer } from "mobx-react";
import { useT } from "../i18n";
import { useIssueDetail } from "../plane";
import { formatMinutes } from "../worklog/format";
import { STATUS_CLASS, dueText, slaText } from "./format";
import { useIssueSla } from "./use-sla";

type Props = { workspaceSlug: string; projectId: string; issueId: string };

export const SlaPanel = observer(function SlaPanel({ workspaceSlug, projectId, issueId }: Props) {
  const t = useT();
  const { issue } = useIssueDetail();
  const current = issue.getIssueById(issueId);
  const version = `${current?.state_id ?? ""}|${current?.priority ?? ""}`;
  const { data } = useIssueSla(workspaceSlug, projectId, issueId, version);
  if (!data) return null;
  const { sla, states } = data;
  if (!sla && states.length === 0) return null;
  return (
    <div data-mawesi="sla-panel" className="space-y-2">
      <h5 className="text-body-xs-medium">{t("sla.panel")}</h5>
      {sla && (
        <div className={`space-y-0.5 rounded-md border-[0.5px] px-2 py-1.5 text-13 ${STATUS_CLASS[sla.status]}`} data-status={sla.status}>
          <div className="font-medium">{slaText(sla, t)}</div>
          <div className="text-11 text-secondary">
            {t("sla.due")}: {dueText(sla.due_at)} · {t("sla.target")}: {formatMinutes(sla.target_minutes)}
          </div>
        </div>
      )}
      {states.length > 0 && (
        <table className="w-full text-13">
          <thead>
            <tr className="text-11 text-tertiary">
              <th className="py-0.5 text-left font-normal">{t("sla.state")}</th>
              <th className="py-0.5 text-right font-normal">{t("sla.business")}</th>
              <th className="py-0.5 text-right font-normal">{t("sla.calendar")}</th>
            </tr>
          </thead>
          <tbody>
            {states.map((s) => (
              <tr key={s.state} data-mawesi="sla-state">
                <td className="py-0.5">
                  {s.state}
                  {s.visits > 1 && <span className="text-11 text-tertiary"> ×{s.visits}</span>}
                </td>
                <td className="py-0.5 text-right">{formatMinutes(s.business_minutes)}</td>
                <td className="py-0.5 text-right text-secondary">{formatMinutes(s.minutes)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
});
