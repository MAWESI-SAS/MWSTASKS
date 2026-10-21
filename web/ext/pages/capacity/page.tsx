/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Capacidad del ciclo (Capacity de Azure DevOps): por persona, horas por día y días libres → horas que le quedan en
 * el ciclo, contra el trabajo restante de sus tareas (estimado − hecho). Rojo si tiene más trabajo que horas.
 * Cada persona edita su fila; un admin edita todas y los días libres del equipo. Se guarda al salir del campo.
 */
import { useState } from "react";
import { observer } from "mobx-react";
import { useParams, useSearchParams } from "react-router";
import useSWR from "swr";
import { CalendarX, X } from "lucide-react";
import { capacityService } from "../../capacity/service";
import type { TCapacityInput, TCapacityMember, TCapacityReport } from "../../capacity/service";
import { useT } from "../../i18n";
import { apiError } from "../../lib/api-error";
import { ButtonAvatars, EUserPermissions, Input, PageHead, TOAST_TYPE, setToast, useUser, useUserPermissions } from "../../plane";
import { formatHours } from "../../worklog/format";

const selectClass = "block h-9 rounded-md border border-subtle bg-surface-1 px-2 text-13 text-primary";

/** Barra de carga: trabajo restante contra capacidad. */
function LoadBar({ work, capacity }: { work: number; capacity: number }) {
  const over = work > capacity;
  const pct = capacity > 0 ? Math.min(100, Math.round((work / capacity) * 100)) : work > 0 ? 100 : 0;
  return (
    <div className="h-2 w-full min-w-24 overflow-hidden rounded-full bg-layer-1" title={`${pct}%`}>
      <div className={`h-full rounded-full ${over ? "bg-danger-primary" : "bg-success-primary"}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function DaysOff({ days, editable, onChange, name }: { days: string[]; editable: boolean; onChange: (d: string[]) => void; name: string }) {
  const t = useT();
  const [value, setValue] = useState("");
  return (
    <div className="flex flex-wrap items-center gap-1">
      {days.map((d) => (
        <span key={d} className="inline-flex items-center gap-0.5 rounded-sm border-[0.5px] border-strong px-1 text-11" data-mawesi="day-off">
          {d.slice(5)}
          {editable && (
            <button type="button" aria-label={t("capacity.remove_day")} onClick={() => onChange(days.filter((x) => x !== d))} className="rounded hover:bg-layer-1">
              <X className="size-3" />
            </button>
          )}
        </span>
      ))}
      {editable && (
        <input
          type="date"
          name={name}
          value={value}
          aria-label={t("capacity.add_day")}
          onChange={(e) => {
            const d = e.target.value;
            setValue("");
            if (d && !days.includes(d)) onChange([...days, d].sort());
          }}
          className="h-6 w-7 cursor-pointer rounded border border-subtle bg-surface-1 text-11 text-transparent [&::-webkit-calendar-picker-indicator]:m-0"
          title={t("capacity.add_day")}
        />
      )}
    </div>
  );
}

const CapacityPage = observer(function CapacityPage() {
  const t = useT();
  const { workspaceSlug = "", projectId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { data: me } = useUser();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const isAdmin = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId) === EUserPermissions.ADMIN;
  const { data: list } = useSWR(workspaceSlug && projectId ? ["mawesi-capacity-cycles", workspaceSlug, projectId] : null, () =>
    capacityService.cycles(workspaceSlug, projectId)
  );
  const cycleId = params.get("ciclo") || list?.current_id || "";
  const { data, error, mutate, isLoading } = useSWR(
    workspaceSlug && projectId && cycleId ? ["mawesi-capacity", workspaceSlug, projectId, cycleId] : null,
    () => capacityService.report(workspaceSlug, projectId, cycleId),
    { revalidateOnFocus: false, shouldRetryOnError: false }
  );
  const [hours, setHours] = useState<Record<string, string>>({});

  const save = async (body: TCapacityInput) => {
    try {
      await mutate(await capacityService.save(workspaceSlug, projectId, cycleId, body), { revalidate: false });
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("capacity.saved") });
    } catch (err) {
      setToast({ type: TOAST_TYPE.ERROR, title: apiError(err, t("worklog.error")) });
    }
  };
  const saveMember = (m: TCapacityMember, patch: Partial<Pick<TCapacityMember, "hours_per_day" | "days_off">>) =>
    save({ members: [{ member_id: m.member_id, hours_per_day: m.hours_per_day, days_off: m.days_off, ...patch }] });
  const commitHours = (m: TCapacityMember) => {
    const raw = hours[m.member_id];
    if (raw === undefined) return;
    const v = Number(raw.replace(",", "."));
    setHours(({ [m.member_id]: _, ...rest }) => rest);
    if (Number.isFinite(v) && v !== m.hours_per_day) void saveMember(m, { hours_per_day: v });
  };

  if (list && list.cycles.length === 0) {
    return <p className="p-4 text-13 text-tertiary">{t("capacity.no_cycles")}</p>;
  }
  const report: TCapacityReport | undefined = data;
  const totals = report?.totals;

  return (
    <>
      <PageHead title={t("capacity.title")} />
      <div className="flex h-full w-full flex-col gap-4 overflow-auto p-4" data-mawesi="capacity">
        <div className="flex flex-wrap items-end gap-4">
          <label className="space-y-1">
            <span className="block text-13 text-secondary">{t("capacity.cycle")}</span>
            <select
              name="cycle"
              className={selectClass}
              value={cycleId}
              onChange={(e) => setParams(new URLSearchParams({ ciclo: e.target.value }), { replace: true })}
            >
              {(list?.cycles ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.start} → {c.end})
                </option>
              ))}
            </select>
          </label>
          {report && totals && (
            <div className="min-w-64 flex-1 space-y-1" data-mawesi="capacity-team">
              <div className="flex items-baseline justify-between gap-2 text-13">
                <span className="font-medium">{t("capacity.team")}</span>
                <span className={totals.remaining_minutes > totals.capacity_left_minutes ? "text-danger-primary" : "text-secondary"}>
                  {formatHours(totals.remaining_minutes)} h {t("capacity.of")} {formatHours(totals.capacity_left_minutes)} h ·{" "}
                  {report.team_days_left} {t("capacity.days_left")}
                </span>
              </div>
              <LoadBar work={totals.remaining_minutes} capacity={totals.capacity_left_minutes} />
            </div>
          )}
        </div>

        {error && <p className="text-13 text-danger-primary">{apiError(error, t("worklog.error"))}</p>}
        {isLoading && <p className="text-13 text-tertiary">{t("report.loading")}</p>}

        {report && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-13">
              <CalendarX className="size-4 text-tertiary" />
              <span className="text-secondary">{t("capacity.team_days_off")}</span>
              <DaysOff
                name="team-day-off"
                days={report.team_days_off}
                editable={isAdmin}
                onChange={(d) => void save({ team_days_off: d })}
              />
              {report.team_days_off.length === 0 && !isAdmin && <span className="text-tertiary">—</span>}
            </div>

            <div className="overflow-x-auto rounded-lg border border-subtle">
              <table className="w-full border-collapse text-13">
                <thead>
                  <tr className="border-b border-subtle text-left text-11 text-secondary">
                    <th className="px-3 py-2 font-medium">{t("capacity.person")}</th>
                    <th className="px-3 py-2 font-medium">{t("capacity.hours_per_day")}</th>
                    <th className="px-3 py-2 font-medium">{t("capacity.days_off")}</th>
                    <th className="px-3 py-2 text-right font-medium">{t("capacity.days_left_col")}</th>
                    <th className="px-3 py-2 text-right font-medium">{t("capacity.capacity")}</th>
                    <th className="px-3 py-2 text-right font-medium">{t("capacity.work")}</th>
                    <th className="w-40 px-3 py-2 font-medium">{t("capacity.load")}</th>
                    <th className="px-3 py-2 text-right font-medium">{t("capacity.done")}</th>
                  </tr>
                </thead>
                <tbody>
                  {report.members.map((m) => {
                    const editable = isAdmin || m.member_id === me?.id;
                    const over = m.remaining_minutes > m.capacity_left_minutes;
                    return (
                      <tr key={m.member_id} className="border-b border-subtle" data-mawesi="capacity-row" data-over={over ? "true" : undefined}>
                        <td className="px-3 py-1.5">
                          <span className="flex items-center gap-2">
                            <ButtonAvatars showTooltip={false} userIds={m.member_id} size="sm" />
                            {m.display_name}
                          </span>
                        </td>
                        <td className="px-3 py-1">
                          <Input
                            name={`hours-${m.display_name}`}
                            type="number"
                            min={0}
                            max={24}
                            step={0.5}
                            disabled={!editable}
                            value={hours[m.member_id] ?? String(m.hours_per_day)}
                            onChange={(e) => setHours((h) => ({ ...h, [m.member_id]: e.target.value }))}
                            onBlur={() => commitHours(m)}
                            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
                            className="w-20"
                          />
                        </td>
                        <td className="px-3 py-1">
                          <DaysOff name={`day-off-${m.display_name}`} days={m.days_off} editable={editable} onChange={(d) => void saveMember(m, { days_off: d })} />
                        </td>
                        <td className="px-3 py-1.5 text-right">{m.days_left}</td>
                        <td className="px-3 py-1.5 text-right">{formatHours(m.capacity_left_minutes)} h</td>
                        <td className={`px-3 py-1.5 text-right ${over ? "font-medium text-danger-primary" : ""}`} data-mawesi="capacity-work">
                          {formatHours(m.remaining_minutes)} h
                          {m.unestimated > 0 && (
                            <span className="block text-11 font-normal text-warning-primary">
                              +{m.unestimated} {t("capacity.unestimated")}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-1.5">
                          <LoadBar work={m.remaining_minutes} capacity={m.capacity_left_minutes} />
                        </td>
                        <td className="px-3 py-1.5 text-right text-secondary">{formatHours(m.completed_minutes)} h</td>
                      </tr>
                    );
                  })}
                  {report.unassigned.count > 0 && (
                    <tr className="text-secondary" data-mawesi="capacity-unassigned">
                      <td className="px-3 py-1.5 italic" colSpan={5}>
                        {t("capacity.unassigned")} ({report.unassigned.count})
                      </td>
                      <td className="px-3 py-1.5 text-right">
                        {formatHours(report.unassigned.remaining_minutes)} h
                        {report.unassigned.unestimated > 0 && (
                          <span className="block text-11 text-warning-primary">
                            +{report.unassigned.unestimated} {t("capacity.unestimated")}
                          </span>
                        )}
                      </td>
                      <td colSpan={2} />
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <p className="text-11 text-tertiary">{t("capacity.help")}</p>
          </>
        )}
      </div>
    </>
  );
});

export default CapacityPage;
