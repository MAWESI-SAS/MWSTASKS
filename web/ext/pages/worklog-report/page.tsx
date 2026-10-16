/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Reporte de horas del workspace: pestaña "Detalle" (filtros, resumen y tabla) y "Por mes" (tablero para facturar).
 * La pestaña va en la URL (?vista=mes) para poder compartirla. Ambas exportan CSV.
 */
import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import { useParams, useSearchParams } from "react-router";
import useSWR from "swr";
import { Download } from "lucide-react";
import { useT } from "../../i18n";
import { Button, Input, PageHead, useProject } from "../../plane";
import { downloadCSV, reportToCSV } from "../../worklog/csv";
import { formatMinutes, todayISO } from "../../worklog/format";
import { REPORT_LIMIT, worklogReportService } from "../../worklog/service";
import { MonthlySummary, type TDrill } from "./monthly";

const firstOfMonth = () => `${todayISO().slice(0, 8)}01`;

const selectClass = "block h-9 rounded-md border border-subtle bg-surface-1 px-2 text-13 text-primary";

function Summary({ title, items }: { title: string; items: Array<[string, number]> }) {
  return (
    <div className="min-w-56 flex-1 rounded-lg border border-subtle p-3">
      <h5 className="mb-2 text-body-xs-medium text-secondary">{title}</h5>
      <ul className="space-y-1">
        {items.map(([label, mins]) => (
          <li key={label} className="flex justify-between gap-4 text-13">
            <span className="truncate">{label}</span>
            <span className="font-medium">{formatMinutes(mins)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const WorklogReportPage = observer(function WorklogReportPage() {
  const t = useT();
  const { workspaceSlug = "" } = useParams();
  const { joinedProjectIds, getProjectById } = useProject();
  const [from, setFrom] = useState(firstOfMonth());
  const [to, setTo] = useState(todayISO());
  const [projectId, setProjectId] = useState("");
  const [memberId, setMemberId] = useState("");
  const [params, setParams] = useSearchParams();
  const monthly = params.get("vista") === "mes";
  const setMonthly = (on: boolean) => setParams(on ? { vista: "mes" } : {}, { replace: true });
  const openDetail = (d: TDrill) => {
    setFrom(d.from);
    setTo(d.to);
    setProjectId(d.projectId);
    setMemberId(d.memberId);
    setMonthly(false);
  };

  const { data, isLoading } = useSWR(workspaceSlug && !monthly ? ["mawesi-report", workspaceSlug, from, to, projectId] : null, () =>
    worklogReportService.report(workspaceSlug, { from, to, ...(projectId ? { project_id: projectId } : {}) })
  );

  const allRows = data?.rows ?? [];
  const members = useMemo(
    () => [...new Map(allRows.map((r) => [r.member_id, r.member_name])).entries()].sort((a, b) => a[1].localeCompare(b[1])),
    [allRows]
  );
  const rows = memberId ? allRows.filter((r) => r.member_id === memberId) : allRows;
  const total = rows.reduce((s, r) => s + r.duration_minutes, 0);
  const sumBy = (key: (r: (typeof rows)[number]) => string) =>
    [...rows.reduce((m, r) => m.set(key(r), (m.get(key(r)) ?? 0) + r.duration_minutes), new Map<string, number>())].sort((a, b) => b[1] - a[1]);

  const exportCSV = () => downloadCSV(reportToCSV(rows), `horas_${workspaceSlug}_${from}_${to}.csv`);

  return (
    <>
      <PageHead title={t("report.title")} />
      <div className="h-full w-full space-y-4 overflow-y-auto p-6" data-mawesi="report">
        <div className="flex w-fit gap-1 rounded-md border border-subtle p-0.5" role="tablist">
          {([false, true] as const).map((on) => (
            <button
              key={String(on)}
              type="button"
              role="tab"
              aria-selected={monthly === on}
              onClick={() => setMonthly(on)}
              className={`rounded px-3 py-1 text-13 ${monthly === on ? "bg-layer-1 font-medium text-primary" : "text-secondary hover:text-primary"}`}
              data-mawesi={on ? "report-tab-monthly" : "report-tab-detail"}
            >
              {t(on ? "report.tab_monthly" : "report.tab_detail")}
            </button>
          ))}
        </div>
        {monthly ? (
          <MonthlySummary workspaceSlug={workspaceSlug} onDrill={openDetail} />
        ) : (
          <>
            <div className="flex flex-wrap items-end gap-3 [&_input]:h-9">
              <label className="space-y-1">
                <span className="block text-13 text-secondary">{t("report.from")}</span>
                <Input type="date" name="from" value={from} max={to} onChange={(e) => setFrom(e.target.value)} />
              </label>
              <label className="space-y-1">
                <span className="block text-13 text-secondary">{t("report.to")}</span>
                <Input type="date" name="to" value={to} min={from} onChange={(e) => setTo(e.target.value)} />
              </label>
              <label className="space-y-1">
                <span className="block text-13 text-secondary">{t("report.project")}</span>
                <select name="project" className={selectClass} value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                  <option value="">{t("report.all")}</option>
                  {joinedProjectIds.map((id) => (
                    <option key={id} value={id}>
                      {getProjectById(id)?.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="block text-13 text-secondary">{t("report.person")}</span>
                <select name="member" className={selectClass} value={memberId} onChange={(e) => setMemberId(e.target.value)}>
                  <option value="">{t("report.all")}</option>
                  {members.map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="ml-auto">
                <Button type="button" variant="secondary" size="lg" onClick={exportCSV} disabled={!rows.length} data-mawesi="report-export">
                  <Download className="size-4" />
                  {t("report.export")}
                </Button>
              </div>
            </div>

            <div className="flex items-baseline gap-3">
              <span className="font-heading text-20 font-bold" data-mawesi="report-total">{formatMinutes(total)}</span>
              <span className="text-13 text-secondary">
                {t("report.total")} · {rows.length} {t("report.entries")}
              </span>
            </div>
            {data && data.count >= REPORT_LIMIT && <p className="text-13 text-warning-primary">{t("report.truncated")}</p>}

            {isLoading ? (
              <p className="text-13 text-tertiary">{t("report.loading")}</p>
            ) : rows.length === 0 ? (
              <p className="text-13 text-tertiary">{t("report.empty")}</p>
            ) : (
              <>
                <div className="flex flex-wrap gap-3">
                  <Summary title={t("report.by_person")} items={sumBy((r) => r.member_name)} />
                  <Summary title={t("report.by_project")} items={sumBy((r) => r.project_identifier)} />
                </div>
                <div className="overflow-x-auto rounded-lg border border-subtle">
                  <table className="w-full text-left text-13" data-mawesi="report-table">
                    <thead className="bg-layer-1 text-secondary">
                      <tr>
                        <th className="px-3 py-2 font-medium">{t("report.date")}</th>
                        <th className="px-3 py-2 font-medium">{t("report.task")}</th>
                        <th className="px-3 py-2 font-medium">{t("report.person")}</th>
                        <th className="px-3 py-2 text-right font-medium">{t("report.time")}</th>
                        <th className="px-3 py-2 font-medium">{t("report.note")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.id} className="border-t border-subtle">
                          <td className="px-3 py-2 whitespace-nowrap">{r.date}</td>
                          <td className="max-w-md px-3 py-2">
                            <a href={`/${workspaceSlug}/browse/${r.project_identifier}-${r.issue_sequence}/`} className="hover:underline">
                              <span className="text-secondary">{r.project_identifier}-{r.issue_sequence}</span> <span className="truncate">{r.issue_name}</span>
                            </a>
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap">{r.member_name}</td>
                          <td className="px-3 py-2 text-right whitespace-nowrap font-medium">{formatMinutes(r.duration_minutes)}</td>
                          <td className="max-w-sm truncate px-3 py-2 text-secondary" title={r.description}>{r.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </>
  );
});

export default WorklogReportPage;
