/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Vista "Tabla" de un proyecto (como la de ClickUp): una fila por tarea, con estado, responsables, vencimiento,
 * horas y cada campo propio como columna. Filtra por lista, busca, ordena y exporta CSV.
 * Admins y miembros editan en la celda (como en ClickUp): estado, prioridad, responsables, vencimiento y campos.
 * El cambio se ve al instante y se guarda por la API de Plane (o la de campos); si falla, vuelve atrás.
 */
import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import { Link, useParams, useSearchParams } from "react-router";
import useSWR from "swr";
import { ArrowDown, ArrowUp, Check, Download } from "lucide-react";
import { groupModules } from "../../folders/group";
import { useT } from "../../i18n";
import {
  Button, ButtonAvatars, DateDropdown, EUserPermissions, Input, MemberDropdown, PageHead, PriorityDropdown, StateDropdown,
  TOAST_TYPE, renderFormattedPayloadDate, setToast, useMember, useModule, useProject, useUserPermissions,
} from "../../plane";
import { PropertyEditor } from "../../properties/property-editor";
import type { TIssuePriorities } from "../../plane";
import type { TProperty, TValue } from "../../properties/service";
import { propertyService } from "../../properties/service";
import { issueService, tableService } from "../../table/service";
import type { TPropValue, TTableProperty, TTableRow } from "../../table/service";
import { cell, downloadCSV } from "../../worklog/csv";
import { formatMinutes } from "../../worklog/format";

const selectClass = "block h-9 rounded-md border border-subtle bg-surface-1 px-2 text-13 text-primary";

type SortKey = "id" | "name" | "state" | "priority" | "due" | "hours" | `p:${string}`;
const PRIORITY_ORDER: Record<string, number> = { urgent: 4, high: 3, medium: 2, low: 1, none: 0 };
type TIssuePatch = Partial<Pick<TTableRow, "state_id" | "priority" | "assignee_ids" | "target_date">>;

const ProjectTablePage = observer(function ProjectTablePage() {
  const t = useT();
  const { workspaceSlug = "", projectId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const moduleId = params.get("module") ?? "";
  const closed = params.get("closed") === "1";
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "id", desc: true });
  const { getPartialProjectById } = useProject();
  const moduleStore = useModule();
  const { getUserDetails } = useMember();
  const identifier = getPartialProjectById(projectId)?.identifier ?? "";
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const role = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId);
  const canEdit = role === EUserPermissions.ADMIN || role === EUserPermissions.MEMBER;

  const { data, isLoading, mutate } = useSWR(
    workspaceSlug && projectId ? ["mawesi-table", workspaceSlug, projectId, moduleId, closed] : null,
    () => tableService.table(workspaceSlug, projectId, { ...(moduleId ? { module: moduleId } : {}), ...(closed ? { closed: "1" as const } : {}) }),
    { revalidateOnFocus: false }
  );
  const tree = groupModules(moduleStore.getProjectModuleDetails(projectId) ?? []);

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const props = data?.properties ?? [];
  const states = data?.states ?? {};
  const optionName = useMemo(() => {
    const m = new Map<string, { name: string; color: string }>();
    props.forEach((p) => p.options.forEach((o) => m.set(o.id, o)));
    return m;
  }, [props]);

  const text = (p: TTableProperty, v: TPropValue): string => {
    if (v === null || v === undefined) return "";
    if (p.type === "select") return optionName.get(String(v))?.name ?? "";
    if (p.type === "multi_select") return (v as string[]).map((id) => optionName.get(id)?.name ?? "").filter(Boolean).join(", ");
    if (p.type === "member") return getUserDetails(String(v))?.display_name ?? "";
    if (p.type === "checkbox") return v ? "✓" : "";
    return String(v);
  };

  const sortValue = (r: TTableRow): string | number => {
    if (sort.key === "id") return r.sequence_id;
    if (sort.key === "name") return r.name.toLowerCase();
    if (sort.key === "state") return r.state_id ? (states[r.state_id]?.name ?? "") : "";
    if (sort.key === "priority") return PRIORITY_ORDER[r.priority] || "";
    if (sort.key === "due") return r.target_date ?? "";
    if (sort.key === "hours") return r.minutes;
    const p = props.find((x) => `p:${x.id}` === sort.key);
    const v = p ? r.values[p.id] : null;
    return p?.type === "number" && typeof v === "number" ? v : p ? text(p, v ?? null).toLowerCase() : "";
  };

  /** Cambia la fila en pantalla al instante y la guarda; si el servidor la rechaza, vuelve atrás. */
  const edit = async (row: TTableRow, local: Partial<TTableRow>, save: () => Promise<Partial<TTableRow> | void>) => {
    const swap = (patch: Partial<TTableRow>) => (d: typeof data) =>
      d && { ...d, rows: d.rows.map((x) => (x.id === row.id ? { ...x, ...patch } : x)) };
    await mutate(swap(local), { revalidate: false });
    try {
      const fromServer = await save();
      if (fromServer) await mutate(swap(fromServer), { revalidate: false });
    } catch {
      await mutate(swap(row), { revalidate: false });
      setToast({ type: TOAST_TYPE.ERROR, title: t("table.save_error") });
    }
  };
  const patchIssue = (row: TTableRow, patch: TIssuePatch) =>
    edit(row, patch, async () => void (await issueService.patchIssue(workspaceSlug, projectId, row.id, patch)));
  const patchValue = (row: TTableRow, propId: string, value: TValue) =>
    edit(row, { values: { ...row.values, [propId]: value } }, async () => ({
      values: { ...row.values, ...(await propertyService.setValues(workspaceSlug, projectId, row.id, { [propId]: value })) },
    }));
  const asProperty = (p: TTableProperty): TProperty => ({ ...p, description: "" });

  const q = query.trim().toLowerCase();
  const rows = (data?.rows ?? [])
    .filter((r) => !q || r.name.toLowerCase().includes(q) || `${identifier}-${r.sequence_id}`.toLowerCase().includes(q))
    .sort((a, b) => {
      const x = sortValue(a);
      const y = sortValue(b);
      const empty = (v: string | number) => v === "" ? 1 : 0; // vacíos siempre al final
      if (empty(x) !== empty(y)) return empty(x) - empty(y);
      const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
      return sort.desc ? -c : c;
    });

  const head = (key: SortKey, label: string, className = "") => (
    <th className={`sticky top-0 z-10 bg-surface-1 px-3 py-2 text-left text-11 font-medium text-secondary ${className}`}>
      <button
        type="button"
        className="flex items-center gap-1 whitespace-nowrap hover:text-primary"
        onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : false }))}
      >
        {label}
        {sort.key === key && (sort.desc ? <ArrowDown className="size-3" /> : <ArrowUp className="size-3" />)}
      </button>
    </th>
  );

  const exportCSV = () => {
    const header = ["ID", t("table.task"), t("table.state"), t("table.priority"), t("table.assignees"), t("table.due"), t("table.hours"), ...props.map((p) => p.name)];
    const lines = rows.map((r) =>
      [
        `${identifier}-${r.sequence_id}`,
        r.name,
        r.state_id ? (states[r.state_id]?.name ?? "") : "",
        r.priority,
        r.assignee_ids.map((id) => getUserDetails(id)?.display_name ?? "").join(", "),
        r.target_date ?? "",
        (r.minutes / 60).toFixed(2).replace(".", ","),
        ...props.map((p) => text(p, r.values[p.id] ?? null)),
      ]
        .map(cell)
        .join(";")
    );
    downloadCSV("﻿" + [header.map(cell).join(";"), ...lines].join("\r\n"), `tabla_${identifier}.csv`);
  };

  const valueCell = (p: TTableProperty, v: TPropValue | undefined) => {
    if (v === null || v === undefined) return null;
    if (p.type === "url")
      return (
        <a href={String(v)} target="_blank" rel="noopener noreferrer" className="text-accent-primary hover:underline">
          {String(v)}
        </a>
      );
    if (p.type === "checkbox") return v ? <Check className="size-4" /> : null;
    if (p.type === "member") return <ButtonAvatars showTooltip userIds={String(v)} size="sm" />;
    if (p.type === "select" || p.type === "multi_select") {
      const ids = p.type === "select" ? [String(v)] : (v as string[]);
      return (
        <div className="flex flex-wrap gap-1">
          {ids.map((id) => {
            const o = optionName.get(id);
            return o ? (
              <span key={id} className="inline-flex items-center gap-1 rounded-sm border-[0.5px] border-strong px-1.5 text-11">
                <span className="size-2 rounded-full" style={{ backgroundColor: o.color || "#94a3b8" }} />
                {o.name}
              </span>
            ) : null;
          })}
        </div>
      );
    }
    return <span>{String(v)}</span>;
  };

  return (
    <>
      <PageHead title={t("table.title")} />
      <div className="flex h-full w-full flex-col gap-3 overflow-hidden p-4" data-mawesi="table">
        <div className="flex flex-wrap items-end gap-3 [&_input]:h-9">
          <label className="space-y-1">
            <span className="block text-13 text-secondary">{t("table.list")}</span>
            <select name="module" className={selectClass} value={moduleId} onChange={(e) => setParam("module", e.target.value)}>
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
          <label className="min-w-56 flex-1 space-y-1">
            <span className="block text-13 text-secondary">&nbsp;</span>
            <Input name="search" value={query} placeholder={t("table.search")} onChange={(e) => setQuery(e.target.value)} className="w-full" />
          </label>
          <label className="flex h-9 items-center gap-2 text-13">
            <input type="checkbox" name="closed" checked={closed} onChange={(e) => setParam("closed", e.target.checked ? "1" : "")} />
            {t("table.closed")}
          </label>
          <span className="flex h-9 items-center text-13 text-secondary" data-mawesi="table-count">
            {rows.length} {t("table.count")}
          </span>
          <Button type="button" variant="secondary" size="lg" onClick={exportCSV} disabled={!rows.length} data-mawesi="table-export">
            <Download className="size-4" />
            {t("table.export")}
          </Button>
        </div>
        {data?.truncated && <p className="text-13 text-warning-primary">{t("table.truncated")}</p>}
        <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-subtle">
          {isLoading ? (
            <p className="p-4 text-13 text-tertiary">{t("table.loading")}</p>
          ) : rows.length === 0 ? (
            <p className="p-4 text-13 text-tertiary">{t("table.empty")}</p>
          ) : (
            <table className="w-full border-collapse text-13">
              <thead>
                <tr className="border-b border-subtle">
                  {head("id", "ID", "left-0 z-20 w-24 min-w-24")}
                  {head("name", t("table.task"), "left-24 z-20 min-w-72 max-w-72 border-r border-subtle")}
                  {head("state", t("table.state"))}
                  {head("priority", t("table.priority"))}
                  <th className="sticky top-0 z-10 bg-surface-1 px-3 py-2 text-left text-11 font-medium text-secondary">{t("table.assignees")}</th>
                  {head("due", t("table.due"))}
                  {head("hours", t("table.hours"))}
                  {props.map((p) => head(`p:${p.id}`, p.name, "min-w-32"))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const state = r.state_id ? states[r.state_id] : undefined;
                  const code = `${identifier}-${r.sequence_id}`;
                  return (
                    <tr key={r.id} className="group border-b border-subtle hover:bg-layer-1" data-mawesi="table-row">
                      {/* ID y Tarea fijas a la izquierda: al editar columnas de la derecha se sigue viendo qué tarea es. */}
                      <td className="sticky left-0 z-[5] w-24 min-w-24 whitespace-nowrap bg-surface-1 px-3 py-1.5 text-tertiary group-hover:bg-layer-1">{code}</td>
                      <td className="sticky left-24 z-[5] min-w-72 max-w-72 border-r border-subtle bg-surface-1 px-3 py-1.5 group-hover:bg-layer-1">
                        <Link to={`/${workspaceSlug}/browse/${code}/`} className="line-clamp-2 hover:underline">
                          {r.name}
                        </Link>
                      </td>
                      <td className="whitespace-nowrap px-3 py-1" data-mawesi="cell-state">
                        {canEdit ? (
                          <StateDropdown
                            value={r.state_id ?? undefined}
                            projectId={projectId}
                            onChange={(state_id: string) => void patchIssue(r, { state_id })}
                            buttonVariant="transparent-with-text"
                            buttonContainerClassName="max-w-40 truncate"
                          />
                        ) : (
                          state && (
                            <span className="inline-flex items-center gap-1.5">
                              <span className="size-2 rounded-full" style={{ backgroundColor: state.color || "#94a3b8" }} />
                              {state.name}
                            </span>
                          )
                        )}
                      </td>
                      <td className="whitespace-nowrap px-3 py-1" data-mawesi="cell-priority">
                        <PriorityDropdown
                          value={r.priority}
                          onChange={(priority: TIssuePriorities) => void patchIssue(r, { priority })}
                          buttonVariant="transparent-with-text"
                          disabled={!canEdit}
                        />
                      </td>
                      <td className="px-3 py-1" data-mawesi="cell-assignees">
                        {canEdit ? (
                          <div className="h-7">
                            <MemberDropdown
                              projectId={projectId}
                              value={r.assignee_ids}
                              onChange={(assignee_ids: string[]) => void patchIssue(r, { assignee_ids })}
                              buttonVariant={r.assignee_ids.length > 0 ? "transparent-without-text" : "transparent-with-text"}
                              placeholder=""
                              multiple
                            />
                          </div>
                        ) : (
                          r.assignee_ids.length > 0 && <ButtonAvatars showTooltip userIds={r.assignee_ids} size="sm" />
                        )}
                      </td>
                      <td className="whitespace-nowrap px-3 py-1" data-mawesi="cell-due">
                        {canEdit ? (
                          <DateDropdown
                            value={r.target_date}
                            onChange={(d: Date | null) => void patchIssue(r, { target_date: d ? renderFormattedPayloadDate(d) ?? null : null })}
                            minDate={r.start_date ? new Date(`${r.start_date}T00:00:00`) : undefined}
                            buttonVariant="transparent-with-text"
                            placeholder=""
                            isClearable
                          />
                        ) : (
                          (r.target_date ?? "")
                        )}
                      </td>
                      <td className="whitespace-nowrap px-3 py-1.5">{r.minutes ? formatMinutes(r.minutes) : ""}</td>
                      {props.map((p) => (
                        <td key={p.id} className="min-w-40 max-w-64 px-1 py-1" title={text(p, r.values[p.id] ?? null)} data-mawesi={`cell-prop-${p.type}`}>
                          {canEdit ? (
                            <PropertyEditor
                              prop={asProperty(p)}
                              value={(r.values[p.id] ?? null) as TValue}
                              projectId={projectId}
                              onSave={(v) => void patchValue(r, p.id, v)}
                            />
                          ) : (
                            <div className="truncate px-2">{valueCell(p, r.values[p.id])}</div>
                          )}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
});

export default ProjectTablePage;
