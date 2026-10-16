/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Tablero "Por mes": horas por cliente (proyecto), persona o lista en cada mes, para facturar.
 * El servidor suma (años de horas sin traer cada registro); cada celda abre el detalle filtrado.
 */
import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { Download } from "lucide-react";
import { useT } from "../../i18n";
import { Button, Input, useProject } from "../../plane";
import { downloadCSV, summaryToCSV } from "../../worklog/csv";
import { formatHours, formatMinutes, monthEnd, monthOf, monthRange } from "../../worklog/format";
import { type TSummaryBy, type TSummaryGroup, worklogReportService } from "../../worklog/service";

export type TDrill = { from: string; to: string; projectId: string; memberId: string };

const selectClass = "block h-9 rounded-md border border-subtle bg-surface-1 px-2 text-13 text-primary";

function Kpi({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div className="min-w-44 flex-1 rounded-lg border border-subtle p-3">
      <div className="text-13 text-secondary">{label}</div>
      <div className="font-heading text-20 font-bold" data-mawesi={testId}>
        {value}
      </div>
    </div>
  );
}

export const MonthlySummary = observer(function MonthlySummary({ workspaceSlug, onDrill }: { workspaceSlug: string; onDrill: (d: TDrill) => void }) {
  const t = useT();
  const { joinedProjectIds, getProjectById } = useProject();
  const [fromMonth, setFromMonth] = useState(monthOf(-11));
  const [toMonth, setToMonth] = useState(monthOf());
  const [projectId, setProjectId] = useState("");
  const [by, setBy] = useState<TSummaryBy>("project");

  const months = useMemo(() => monthRange(fromMonth, toMonth), [fromMonth, toMonth]);
  const valid = months.length > 0;
  const { data, isLoading } = useSWR(
    workspaceSlug && valid ? ["mawesi-summary", workspaceSlug, fromMonth, toMonth, projectId, by] : null,
    () =>
      worklogReportService.summary(workspaceSlug, {
        from: `${fromMonth}-01`,
        to: monthEnd(toMonth),
        by,
        ...(projectId ? { project_id: projectId } : {}),
      })
  );

  const groups = data?.groups ?? [];
  const label = (g: TSummaryGroup) => {
    const name = g.label || (by === "module" ? t("report.no_list") : "—");
    return by === "module" && !projectId && g.project_identifier ? `${g.project_identifier} · ${name}` : name;
  };
  const columnTotals = useMemo(
    () => Object.fromEntries(months.map((m) => [m, groups.reduce((s, g) => s + (g.cells[m] ?? 0), 0)])),
    [months, groups]
  );
  const total = data?.total_minutes ?? 0;
  const top = months.reduce<string | null>((best, m) => (columnTotals[m] > (best ? columnTotals[best] : 0) ? m : best), null);

  const drill = (g: TSummaryGroup | null, from: string, to: string) =>
    onDrill({
      from,
      to,
      projectId: g?.project_id ?? projectId,
      memberId: g && by === "member" ? g.key : "",
    });

  const exportCSV = () => {
    // Encabezados fijos en español, como el CSV del Detalle (Excel en español).
    const rows = [...groups.map((g) => ({ label: label(g), cells: g.cells, total: g.total })), { label: "Total", cells: columnTotals, total }];
    const head = { project: "Cliente", member: "Persona", module: "Lista" }[by];
    downloadCSV(summaryToCSV(head, months, rows), `horas_por_mes_${workspaceSlug}_${fromMonth}_${toMonth}.csv`);
  };

  const cellButton = "w-full rounded px-1 text-right hover:bg-layer-1 hover:underline";

  return (
    <div className="space-y-4" data-mawesi="report-monthly">
      <div className="flex flex-wrap items-end gap-3 [&_input]:h-9">
        <label className="space-y-1">
          <span className="block text-13 text-secondary">{t("report.month_from")}</span>
          <Input type="month" name="from_month" value={fromMonth} max={toMonth} onChange={(e) => e.target.value && setFromMonth(e.target.value)} />
        </label>
        <label className="space-y-1">
          <span className="block text-13 text-secondary">{t("report.month_to")}</span>
          <Input type="month" name="to_month" value={toMonth} min={fromMonth} onChange={(e) => e.target.value && setToMonth(e.target.value)} />
        </label>
        <label className="space-y-1">
          <span className="block text-13 text-secondary">{t("report.project")}</span>
          <select name="summary_project" className={selectClass} value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            <option value="">{t("report.all")}</option>
            {joinedProjectIds.map((id) => (
              <option key={id} value={id}>
                {getProjectById(id)?.name}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="block text-13 text-secondary">{t("report.group_by")}</span>
          <select name="group_by" className={selectClass} value={by} onChange={(e) => setBy(e.target.value as TSummaryBy)}>
            <option value="project">{t("report.by_client")}</option>
            <option value="member">{t("report.by_member")}</option>
            <option value="module">{t("report.by_list")}</option>
          </select>
        </label>
        <div className="ml-auto">
          <Button type="button" variant="secondary" size="lg" onClick={exportCSV} disabled={!groups.length} data-mawesi="summary-export">
            <Download className="size-4" />
            {t("report.export")}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <Kpi label={t("report.total")} value={formatMinutes(total)} testId="summary-total" />
        <Kpi label={t("report.avg_month")} value={valid ? `${formatHours(Math.round(total / months.length))} h` : "—"} />
        <Kpi label={t("report.top_month")} value={top ? `${top} · ${formatHours(columnTotals[top])} h` : "—"} />
      </div>

      {isLoading ? (
        <p className="text-13 text-tertiary">{t("report.loading")}</p>
      ) : groups.length === 0 ? (
        <p className="text-13 text-tertiary">{t("report.empty")}</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-subtle">
          <table className="w-full text-left text-13 tabular-nums" data-mawesi="summary-table">
            <thead className="bg-layer-1 text-secondary">
              <tr>
                <th className="sticky left-0 z-10 bg-layer-1 px-3 py-2 font-medium">
                  {{ project: t("report.by_client"), member: t("report.by_member"), module: t("report.by_list") }[by]}
                </th>
                {months.map((m) => (
                  <th key={m} className="px-2 py-2 text-right font-medium whitespace-nowrap">
                    {m}
                  </th>
                ))}
                <th className="px-3 py-2 text-right font-medium">{t("report.total")}</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <tr key={g.key} className="group border-t border-subtle" data-mawesi="summary-row">
                  <td className="sticky left-0 max-w-72 truncate bg-surface-1 px-3 py-2 group-hover:bg-layer-1" title={label(g)}>
                    {label(g)}
                  </td>
                  {months.map((m) => (
                    <td key={m} className="px-1 py-1 text-right whitespace-nowrap">
                      {g.cells[m] ? (
                        <button type="button" className={cellButton} title={t("report.drill")} onClick={() => drill(g, `${m}-01`, monthEnd(m))} data-mawesi={`summary-cell-${m}`}>
                          {formatHours(g.cells[m])}
                        </button>
                      ) : (
                        <span className="px-1 text-tertiary">·</span>
                      )}
                    </td>
                  ))}
                  <td className="px-1 py-1 text-right font-medium whitespace-nowrap">
                    <button type="button" className={cellButton} title={t("report.drill")} onClick={() => drill(g, `${fromMonth}-01`, monthEnd(toMonth))}>
                      {formatHours(g.total)}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-layer-1 font-medium">
              <tr className="border-t border-subtle">
                <td className="sticky left-0 bg-layer-1 px-3 py-2">{t("report.total")}</td>
                {months.map((m) => (
                  <td key={m} className="px-2 py-2 text-right whitespace-nowrap" data-mawesi={`summary-month-${m}`}>
                    {columnTotals[m] ? formatHours(columnTotals[m]) : "·"}
                  </td>
                ))}
                <td className="px-3 py-2 text-right whitespace-nowrap">{formatHours(total)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
});
