/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Flujo del proyecto (widgets de analítica de Azure DevOps): flujo acumulado por estado, lead time y cycle time,
 * tareas terminadas por semana y las tareas en curso más viejas. Se puede acotar a una lista. Las terminadas no se
 * apilan por defecto (como "ocultar la columna Done" de Azure DevOps): con años de historia tapan las abiertas.
 */
import { useMemo } from "react";
import { observer } from "mobx-react";
import { Link, useParams, useSearchParams } from "react-router";
import useSWR from "swr";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import { groupModules } from "../../folders/group";
import { FLOW_WINDOWS, flowService } from "../../flow/service";
import type { TFlowStats } from "../../flow/service";
import { useT } from "../../i18n";
import { apiError } from "../../lib/api-error";
import { PageHead, useModule, useProjectState } from "../../plane";

const selectClass = "block h-9 rounded-md border border-subtle bg-surface-1 px-2 text-13 text-primary";
const AXIS = { fontSize: 11, fill: "var(--text-color-tertiary, #8b8d98)" };

function StatCard({ label, stats, help, testId }: { label: string; stats: TFlowStats; help: string; testId: string }) {
  const t = useT();
  const v = (n: number | null) => (n === null ? "—" : n.toLocaleString(undefined, { maximumFractionDigits: 1 }));
  return (
    <div className="space-y-1 rounded-lg border border-subtle p-3" data-mawesi={testId}>
      <div className="text-11 text-tertiary">{label}</div>
      <div className="font-heading text-24 font-semibold">
        {v(stats.avg)} <span className="text-13 font-normal text-secondary">{t("flow.days")}</span>
      </div>
      <div className="text-11 text-secondary">
        {t("flow.median")} {v(stats.p50)} · 85% ≤ {v(stats.p85)} · {stats.count} {t("flow.items")}
      </div>
      <div className="text-11 text-tertiary">{help}</div>
    </div>
  );
}

const FlowPage = observer(function FlowPage() {
  const t = useT();
  const { workspaceSlug = "", projectId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const days = Number(params.get("dias")) || 30;
  const moduleId = params.get("lista") ?? "";
  const withDone = params.get("terminadas") === "1";
  const moduleStore = useModule();
  const { getStateById } = useProjectState();
  useSWR(workspaceSlug && projectId ? ["mawesi-flow-modules", workspaceSlug, projectId] : null, () => moduleStore.fetchModules(workspaceSlug, projectId), {
    revalidateOnFocus: false,
  });
  const tree = groupModules(moduleStore.getProjectModuleDetails(projectId) ?? []);
  const { data, error, isLoading } = useSWR(
    workspaceSlug && projectId ? ["mawesi-flow", workspaceSlug, projectId, days, moduleId] : null,
    () => flowService.flow(workspaceSlug, projectId, days, moduleId || undefined),
    { revalidateOnFocus: false, shouldRetryOnError: false }
  );

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  // Recharts quiere una fila por día; se apila de abajo hacia arriba en orden inverso (terminadas abajo).
  const rows = useMemo(
    () => (data ? data.days.map((d, i) => ({ day: d.slice(5), ...Object.fromEntries(data.states.map((s) => [s.id, data.cfd[s.id][i]])) })) : []),
    [data]
  );
  const stacked = data ? [...data.states].reverse().filter((s) => withDone || s.group !== "completed") : [];

  return (
    <>
      <PageHead title={t("flow.title")} />
      <div className="flex h-full w-full flex-col gap-4 overflow-auto p-4" data-mawesi="flow">
        <div className="flex flex-wrap items-end gap-3">
          <label className="space-y-1">
            <span className="block text-13 text-secondary">{t("flow.window")}</span>
            <select name="days" className={selectClass} value={days} onChange={(e) => setParam("dias", e.target.value)}>
              {FLOW_WINDOWS.map((w) => (
                <option key={w} value={w}>
                  {t("flow.last")} {w} {t("flow.days")}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span className="block text-13 text-secondary">{t("table.list")}</span>
            <select name="module" className={selectClass} value={moduleId} onChange={(e) => setParam("lista", e.target.value)}>
              <option value="">{t("table.all_lists")}</option>
              {tree.folders.map((f) => (
                <optgroup key={f.name} label={f.name}>
                  {f.lists.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </optgroup>
              ))}
              {tree.loose.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex h-9 items-center gap-2 text-13">
            <input type="checkbox" name="with-done" checked={withDone} onChange={(e) => setParam("terminadas", e.target.checked ? "1" : "")} />
            {t("flow.with_done")}
          </label>
          {data && (
            <span className="flex h-9 items-center text-13 text-secondary" data-mawesi="flow-wip">
              {t("flow.wip")}: {data.wip}
            </span>
          )}
        </div>

        {error && <p className="text-13 text-danger-primary">{apiError(error, t("worklog.error"))}</p>}
        {isLoading && <p className="text-13 text-tertiary">{t("report.loading")}</p>}

        {data && (
          <>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <StatCard label={t("flow.lead_time")} stats={data.lead_time} help={t("flow.lead_help")} testId="flow-lead" />
              <StatCard
                label={t("flow.cycle_time")}
                stats={data.cycle_time}
                help={data.cycle_time_missing ? `${t("flow.cycle_help")} ${data.cycle_time_missing} ${t("flow.cycle_missing")}` : t("flow.cycle_help")}
                testId="flow-cycle"
              />
            </div>

            <section className="space-y-2 rounded-lg border border-subtle p-3" data-mawesi="flow-cfd">
              <h4 className="text-14 font-medium">{t("flow.cfd")}</h4>
              <p className="text-11 text-tertiary">{t("flow.cfd_help")}</p>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color-subtle, #e4e4e7)" vertical={false} />
                    <XAxis dataKey="day" tick={AXIS} minTickGap={24} />
                    <YAxis tick={AXIS} allowDecimals={false} />
                    <ChartTooltip contentStyle={{ fontSize: 12 }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {stacked.map((s) => (
                      <Area key={s.id} type="monotone" dataKey={s.id} name={s.name} stackId="cfd" stroke={s.color} fill={s.color} fillOpacity={0.55} isAnimationActive={false} />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              <section className="space-y-2 rounded-lg border border-subtle p-3" data-mawesi="flow-throughput">
                <h4 className="text-14 font-medium">{t("flow.throughput")}</h4>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.throughput.map((w) => ({ week: w.start.slice(5), done: w.done }))} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color-subtle, #e4e4e7)" vertical={false} />
                      <XAxis dataKey="week" tick={AXIS} />
                      <YAxis tick={AXIS} allowDecimals={false} />
                      <ChartTooltip contentStyle={{ fontSize: 12 }} />
                      <Bar dataKey="done" name={t("flow.done_items")} fill="var(--mawesi-card-green)" isAnimationActive={false} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>

              <section className="space-y-2 rounded-lg border border-subtle p-3" data-mawesi="flow-aging">
                <h4 className="text-14 font-medium">{t("flow.aging")}</h4>
                {data.aging.length === 0 ? (
                  <p className="text-13 text-tertiary">{t("flow.no_aging")}</p>
                ) : (
                  <ul className="divide-y divide-subtle text-13">
                    {data.aging.map((a) => (
                      <li key={a.id} className="flex items-center gap-2 py-1.5" data-mawesi="flow-aging-item">
                        <span className="w-16 flex-shrink-0 text-tertiary">{a.key}</span>
                        <Link to={`/${workspaceSlug}/browse/${a.key}/`} className="min-w-0 flex-1 truncate hover:underline">
                          {a.name}
                        </Link>
                        <span className="flex-shrink-0 text-11 text-secondary">{getStateById(a.state_id)?.name}</span>
                        <span className="w-16 flex-shrink-0 text-right font-medium">
                          {a.age_days.toLocaleString(undefined, { maximumFractionDigits: 1 })} {t("flow.days")}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </>
        )}
      </div>
    </>
  );
});

export default FlowPage;
