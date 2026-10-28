/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Carga de trabajo (la vista Workload de ClickUp): una fila por persona y una columna por día, con las horas que le
 * tocan de sus tareas abiertas contra su capacidad. Rojo si se pasa. Clic en una celda: qué tareas la forman. "Sin
 * programar": lo que no entra en la grilla (sin fechas, vencido, sin estimado). Rango, medida y proyecto van en la URL.
 * Las reglas del cálculo están en backend/plane_mawesi/workload.py.
 */
import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import { Link, useParams, useSearchParams } from "react-router";
import useSWR from "swr";
import { CalendarClock, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useT } from "../../i18n";
import { apiError } from "../../lib/api-error";
import { ButtonAvatars, EUserWorkspaceRoles, Input, PageHead, TOAST_TYPE, setToast, useProject, useUserPermissions } from "../../plane";
import { formatHours, todayISO } from "../../worklog/format";
import { dayLabel, rangeOf, shift, type TRange } from "../../workload/dates";
import { workloadService } from "../../workload/service";
import type { TWorkloadRow, TWorkloadTask } from "../../workload/service";

type TMeasure = "horas" | "tareas" | "pct";
const selectClass = "block h-8 rounded-md border border-subtle bg-surface-1 px-2 text-13 text-primary";
const RANGES: TRange[] = ["semana", "2semanas", "mes"];
const MEASURES: TMeasure[] = ["horas", "tareas", "pct"];

/** Color de una celda: verde dentro de la capacidad, rojo si se pasa (o si cae trabajo en un día sin capacidad). */
function tone(minutes: number, capacity: number): string {
  if (!minutes) return "";
  if (minutes > capacity) return "bg-danger-subtle text-danger-primary";
  return "bg-success-subtle text-success-primary";
}

function TaskLine({ task, ws, extra }: { task: TWorkloadTask; ws: string; extra?: string }) {
  return (
    <li className="flex items-baseline gap-2 py-1 text-13" data-mawesi="workload-task">
      <Link to={`/${ws}/browse/${task.key}/`} className="shrink-0 font-medium text-accent-primary hover:underline">
        {task.key}
      </Link>
      <span className="min-w-0 flex-1 truncate" title={task.name}>
        {task.name}
      </span>
      {extra && <span className="shrink-0 text-secondary">{extra}</span>}
    </li>
  );
}

const WorkloadPage = observer(function WorkloadPage() {
  const t = useT();
  const { workspaceSlug = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { joinedProjectIds, getProjectById } = useProject();
  const { getWorkspaceRoleByWorkspaceSlug } = useUserPermissions();
  const isAdmin = getWorkspaceRoleByWorkspaceSlug(workspaceSlug) === EUserWorkspaceRoles.ADMIN;
  const range = (RANGES.includes(params.get("rango") as TRange) ? params.get("rango") : "2semanas") as TRange;
  const measure = (MEASURES.includes(params.get("medida") as TMeasure) ? params.get("medida") : "horas") as TMeasure;
  const anchor = params.get("desde") || todayISO();
  const project = params.get("proyecto") || "";
  const [from, to] = rangeOf(anchor, range);
  const set = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next, { replace: true });
  };
  const [cell, setCell] = useState<{ member: string; date: string } | null>(null);
  const [backlog, setBacklog] = useState(false);
  const [editing, setEditing] = useState<Record<string, string>>({});

  const key = workspaceSlug ? ["mawesi-workload", workspaceSlug, from, to, project] : null;
  const { data, error, isLoading, mutate } = useSWR(key, () => workloadService.report(workspaceSlug, { from, to, ...(project ? { project } : {}) }), {
    revalidateOnFocus: false,
  });
  const locale = typeof navigator !== "undefined" ? navigator.language : "es";
  const rowKey = (r: TWorkloadRow) => r.member_id ?? "";
  const selected = useMemo(() => data?.rows.find((r) => rowKey(r) === cell?.member), [data, cell]);
  // "Sin asignar" va en la grilla solo si tiene algo en el rango; lo suyo sin fechas sigue en "Sin programar".
  const gridRows = useMemo(() => (data?.rows ?? []).filter((r) => r.member_id || r.items.length), [data]);

  const value = (r: TWorkloadRow, date: string): string => {
    const m = r.minutes[date] ?? 0;
    if (measure === "tareas") return r.tasks[date] ? String(r.tasks[date]) : "";
    if (!m) return "";
    if (measure === "pct") {
      const cap = r.capacity[date] ?? 0;
      return cap ? `${Math.round((m / cap) * 100)}%` : "!";
    }
    return `${formatHours(m)} h`;
  };

  const saveHours = async (r: TWorkloadRow) => {
    const raw = editing[rowKey(r)];
    setEditing(({ [rowKey(r)]: _, ...rest }) => rest);
    if (raw === undefined || !r.member_id) return;
    const v = Number(raw.replace(",", "."));
    if (!Number.isFinite(v) || v === r.hours_per_day) return;
    try {
      await workloadService.setCapacity(workspaceSlug, r.member_id, v);
      await mutate();
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("workload.saved") });
    } catch (err) {
      setToast({ type: TOAST_TYPE.ERROR, title: apiError(err, t("worklog.error")) });
    }
  };

  const cellTasks = selected && cell
    ? measure === "tareas"
      ? selected.items.filter((i) => (i.start ?? i.end ?? "") <= cell.date && cell.date <= (i.end ?? i.start ?? ""))
      : selected.items.filter((i) => i.days[cell.date])
    : [];

  return (
    <>
      <PageHead title={t("workload.title")} />
      <div className="flex h-full w-full flex-col gap-3 overflow-hidden p-4" data-mawesi="workload">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1">
            <button type="button" aria-label={t("workload.prev")} onClick={() => set({ desde: shift(anchor, range, -1) })} className="rounded p-1 hover:bg-layer-1" data-mawesi="workload-prev">
              <ChevronLeft className="size-4" />
            </button>
            <button type="button" onClick={() => set({ desde: "" })} className="rounded border border-subtle px-2 py-1 text-13 hover:bg-layer-1">
              {t("workload.today")}
            </button>
            <button type="button" aria-label={t("workload.next")} onClick={() => set({ desde: shift(anchor, range, 1) })} className="rounded p-1 hover:bg-layer-1" data-mawesi="workload-next">
              <ChevronRight className="size-4" />
            </button>
            <span className="ml-1 text-13 text-secondary" data-mawesi="workload-range">
              {from} → {to}
            </span>
          </div>
          <select name="range" aria-label={t("workload.range")} className={selectClass} value={range} onChange={(e) => set({ rango: e.target.value })}>
            {RANGES.map((r) => (
              <option key={r} value={r}>
                {t(`workload.range_${r}`)}
              </option>
            ))}
          </select>
          <select name="measure" aria-label={t("workload.measure")} className={selectClass} value={measure} onChange={(e) => set({ medida: e.target.value })}>
            {MEASURES.map((m) => (
              <option key={m} value={m}>
                {t(`workload.measure_${m}`)}
              </option>
            ))}
          </select>
          <select name="project" aria-label={t("workload.project")} className={selectClass} value={project} onChange={(e) => set({ proyecto: e.target.value })}>
            <option value="">{t("workload.all_projects")}</option>
            {(joinedProjectIds ?? []).map((id) => (
              <option key={id} value={id}>
                {getProjectById(id)?.name ?? id}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setBacklog((b) => !b)}
            className={`ml-auto flex items-center gap-1 rounded border px-2 py-1 text-13 ${backlog ? "border-accent-strong bg-accent-subtle" : "border-subtle hover:bg-layer-1"}`}
            data-mawesi="workload-backlog-toggle"
          >
            <CalendarClock className="size-4" />
            {t("workload.backlog")}
          </button>
        </div>
        <p className="text-11 text-tertiary">{t("workload.help")}</p>

        {error && <p className="text-13 text-danger-primary">{apiError(error, t("worklog.error"))}</p>}
        {isLoading && <p className="text-13 text-tertiary">{t("report.loading")}</p>}
        {data && data.rows.length === 0 && <p className="text-13 text-tertiary">{t("workload.empty")}</p>}

        {data && data.rows.length > 0 && (
          <div className="flex min-h-0 flex-1 gap-3">
            <div className="min-w-0 flex-1 overflow-auto rounded-lg border border-subtle">
              <table className="border-collapse text-13" data-mawesi="workload-grid">
                <thead className="sticky top-0 z-10 bg-surface-1">
                  <tr className="border-b border-subtle text-11 text-secondary">
                    <th className="sticky left-0 z-20 min-w-56 bg-surface-1 px-3 py-2 text-left font-medium">{t("workload.person")}</th>
                    {data.days.map((d) => {
                      const l = dayLabel(d.date, locale);
                      return (
                        <th
                          key={d.date}
                          className={`min-w-14 px-1 py-1 text-center font-medium ${d.workday ? "" : "bg-layer-1"} ${d.date === data.today ? "text-accent-primary" : ""}`}
                          title={d.workday ? d.date : `${d.date} · ${t("workload.non_workday")}`}
                        >
                          <div className="capitalize">{l.weekday}</div>
                          <div className="text-13 text-primary">
                            {l.day} <span className="text-11 text-tertiary">{l.month}</span>
                          </div>
                        </th>
                      );
                    })}
                    <th className="min-w-28 px-3 py-2 text-right font-medium">{t("workload.total")}</th>
                  </tr>
                </thead>
                <tbody>
                  {gridRows.map((r) => {
                    const id = rowKey(r);
                    const over = r.total_minutes > r.capacity_minutes;
                    return (
                      <tr key={id || "nadie"} className="border-b border-subtle" data-mawesi="workload-row" data-member={r.display_name || "sin-asignar"}>
                        <td className="sticky left-0 z-10 bg-surface-1 px-3 py-1.5">
                          <div className="flex items-center gap-2">
                            {r.member_id ? <ButtonAvatars showTooltip={false} userIds={r.member_id} size="sm" /> : null}
                            <span className="truncate font-medium">{r.member_id ? r.display_name || r.email : t("workload.unassigned")}</span>
                          </div>
                          {r.member_id && (
                            <div className="mt-0.5 flex items-center gap-1 text-11 text-tertiary">
                              {isAdmin ? (
                                <Input
                                  name={`capacity-${r.display_name}`}
                                  type="number"
                                  min={0}
                                  max={24}
                                  step={0.5}
                                  value={editing[id] ?? String(r.hours_per_day)}
                                  onChange={(e) => setEditing((h) => ({ ...h, [id]: e.target.value }))}
                                  onBlur={() => void saveHours(r)}
                                  onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
                                  className="h-6 w-14 px-1 text-11"
                                  aria-label={t("workload.hours_per_day")}
                                />
                              ) : (
                                <span>{formatHours(r.hours_per_day * 60)}</span>
                              )}
                              <span>{t("workload.h_per_day")}</span>
                            </div>
                          )}
                        </td>
                        {data.days.map((d) => {
                          const m = r.minutes[d.date] ?? 0;
                          const cap = r.capacity[d.date] ?? 0;
                          const v = value(r, d.date);
                          const active = cell?.member === id && cell.date === d.date;
                          return (
                            <td key={d.date} className={`p-0.5 text-center ${d.workday ? "" : "bg-layer-1"}`}>
                              {v ? (
                                <button
                                  type="button"
                                  onClick={() => setCell(active ? null : { member: id, date: d.date })}
                                  className={`h-8 w-full rounded text-11 font-medium ${measure === "tareas" ? "bg-layer-2 text-primary" : r.member_id ? tone(m, cap) : "bg-layer-2 text-secondary"} ${active ? "ring-2 ring-accent-strong" : ""}`}
                                  title={r.member_id && measure !== "tareas" ? `${formatHours(m)} h / ${formatHours(cap)} h` : undefined}
                                  data-mawesi="workload-cell"
                                  data-date={d.date}
                                  data-over={r.member_id && m > cap ? "true" : undefined}
                                >
                                  {v}
                                </button>
                              ) : null}
                            </td>
                          );
                        })}
                        <td className={`px-3 py-1.5 text-right text-13 ${r.member_id && over && measure !== "tareas" ? "text-danger-primary" : "text-secondary"}`} data-mawesi="workload-total">
                          {measure === "tareas"
                            ? r.items.length
                            : r.member_id
                              ? `${formatHours(r.total_minutes)} / ${formatHours(r.capacity_minutes)} h`
                              : `${formatHours(r.total_minutes)} h`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {(cell && selected) || backlog ? (
              <aside className="w-96 shrink-0 overflow-y-auto rounded-lg border border-subtle p-3" data-mawesi="workload-side">
                {cell && selected && (
                  <section className="mb-4" data-mawesi="workload-detail">
                    <div className="mb-1 flex items-center justify-between">
                      <h4 className="text-13 font-medium">
                        {selected.member_id ? selected.display_name : t("workload.unassigned")} · {cell.date}
                      </h4>
                      <button type="button" aria-label={t("worklog.cancel")} onClick={() => setCell(null)} className="rounded p-0.5 hover:bg-layer-1">
                        <X className="size-4" />
                      </button>
                    </div>
                    <ul className="divide-y divide-subtle">
                      {cellTasks.map((i) => (
                        <TaskLine key={i.id} task={i} ws={workspaceSlug} extra={measure === "tareas" ? undefined : `${formatHours(i.days[cell.date] ?? 0)} h`} />
                      ))}
                    </ul>
                  </section>
                )}
                {backlog && (
                  <section data-mawesi="workload-backlog">
                    <h4 className="mb-1 text-13 font-medium">{t("workload.backlog")}</h4>
                    <p className="mb-2 text-11 text-tertiary">{t("workload.backlog_help")}</p>
                    {data.rows.map((r) => {
                      const b = r.backlog;
                      if (!b.undated_count && !b.overdue_count && !b.unestimated) return null;
                      return (
                        <details key={rowKey(r) || "nadie"} className="mb-2 rounded border border-subtle px-2 py-1" data-mawesi="workload-backlog-row">
                          <summary className="cursor-pointer text-13">
                            <span className="font-medium">{r.member_id ? r.display_name || r.email : t("workload.unassigned")}</span>
                            <span className="ml-2 text-11 text-secondary">
                              {t("workload.undated")}: {b.undated_count} · {t("workload.overdue")}: {b.overdue_count} · {t("workload.unestimated")}: {b.unestimated}
                            </span>
                          </summary>
                          {b.overdue.length > 0 && <p className="mt-1 text-11 font-medium text-danger-primary">{t("workload.overdue")}</p>}
                          <ul>
                            {b.overdue.map((x) => (
                              <TaskLine key={`o${x.id}`} task={x} ws={workspaceSlug} extra={x.end ?? ""} />
                            ))}
                          </ul>
                          {b.undated.length > 0 && <p className="mt-1 text-11 font-medium text-secondary">{t("workload.undated")}</p>}
                          <ul>
                            {b.undated.map((x) => (
                              <TaskLine key={`u${x.id}`} task={x} ws={workspaceSlug} extra={x.remaining_minutes != null ? `${formatHours(x.remaining_minutes)} h` : undefined} />
                            ))}
                          </ul>
                        </details>
                      );
                    })}
                  </section>
                )}
              </aside>
            ) : null}
          </div>
        )}
        {data?.truncated && <p className="text-11 text-tertiary">{t("workload.truncated")}</p>}
      </div>
    </>
  );
});

export default WorkloadPage;
