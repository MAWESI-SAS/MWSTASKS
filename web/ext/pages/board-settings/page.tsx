/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Configuración del proyecto → Tablero (como Azure DevOps Boards; solo admins editan):
 * - Por columna: límite de tareas en curso (WIP) y definición de terminado.
 * - Colores de tarjeta: reglas en orden; gana la primera que coincide.
 * - Dependencias: frenar, soltar de "Blocked" y correr fechas (backend plane_mawesi/dependencies.py).
 */
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR, { mutate as globalMutate } from "swr";
import { ArrowDown, ArrowUp, SquareKanban, Plus, Trash2 } from "lucide-react";
import { CARD_COLORS, boardService } from "../../board/service";
import type { TBoardConfig, TCardColor, TCardRule, TDependencyPolicy } from "../../board/service";
import { boardKey } from "../../board/use-board";
import { useT } from "../../i18n";
import type { TKey } from "../../i18n";
import { apiError } from "../../lib/api-error";
import {
  BreadcrumbLink, Breadcrumbs, Button, EUserPermissions, Input, PageHead, SettingsContentWrapper, SettingsPageHeader, TextArea,
  TOAST_TYPE, setToast, useLabel, useProjectState, useUserPermissions,
} from "../../plane";
import { PRIORITIES } from "../../sla/service";
import { Toggle } from "../../ui/toggle";

const DEPENDENCIES: TDependencyPolicy = { enforce: true, auto_unblock: true, reschedule: true };
const EMPTY: TBoardConfig = { limits: {}, card_rules: [], dependencies: DEPENDENCIES };
const selectClass = "block h-8 rounded-md border border-subtle bg-surface-1 px-2 text-13 text-primary disabled:opacity-60";
const newRule = (): TCardRule => ({ name: "", color: "red", conditions: { overdue: true }, enabled: true });

function BoardHeader() {
  const t = useT();
  return (
    <SettingsPageHeader
      leftItem={
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label={t("board.settings_title")} icon={<SquareKanban className="size-4 text-tertiary" />} />} />
        </Breadcrumbs>
      }
    />
  );
}

const Swatch = ({ color }: { color: TCardColor }) => (
  <span className="inline-block size-3 flex-shrink-0 rounded-full" style={{ backgroundColor: `var(--mawesi-card-${color})` }} />
);

const BoardSettingsPage = observer(function BoardSettingsPage() {
  const t = useT();
  const { workspaceSlug = "", projectId = "" } = useParams();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const isAdmin = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId) === EUserPermissions.ADMIN;
  const stateStore = useProjectState();
  const labelStore = useLabel();
  useSWR(workspaceSlug && projectId ? ["mawesi-board-states", workspaceSlug, projectId] : null, () =>
    Promise.all([stateStore.fetchProjectStates(workspaceSlug, projectId), labelStore.fetchProjectLabels(workspaceSlug, projectId)])
  );
  const states = stateStore.getProjectStates(projectId) ?? [];
  const labels = labelStore.getProjectLabels(projectId) ?? [];
  const { data: saved, isLoading } = useSWR(workspaceSlug && projectId ? boardKey(workspaceSlug, projectId) : null, () =>
    boardService.config(workspaceSlug, projectId)
  );
  const [form, setForm] = useState<TBoardConfig>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isLoading) setForm(saved ?? EMPTY);
  }, [saved, isLoading]);

  const disabled = !isAdmin || saving;
  const limitOf = (id: string) => form.limits[id] ?? { wip_limit: null, definition_of_done: "" };
  const setLimit = (id: string, patch: Partial<TBoardConfig["limits"][string]>) =>
    setForm((f) => ({ ...f, limits: { ...f.limits, [id]: { ...limitOf(id), ...patch } } }));
  const setRule = (i: number, patch: Partial<TCardRule>) =>
    setForm((f) => ({ ...f, card_rules: f.card_rules.map((r, j) => (j === i ? { ...r, ...patch } : r)) }));
  const setCond = (i: number, patch: Partial<TCardRule["conditions"]>) =>
    setForm((f) => ({ ...f, card_rules: f.card_rules.map((r, j) => (j === i ? { ...r, conditions: { ...r.conditions, ...patch } } : r)) }));
  const toggleIn = (list: string[] | undefined, id: string, on: boolean) =>
    on ? [...(list ?? []), id] : (list ?? []).filter((x) => x !== id);
  const move = (i: number, d: -1 | 1) =>
    setForm((f) => {
      const rules = [...f.card_rules];
      [rules[i], rules[i + d]] = [rules[i + d], rules[i]];
      return { ...f, card_rules: rules };
    });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const data = await boardService.save(workspaceSlug, projectId, form);
      await globalMutate(boardKey(workspaceSlug, projectId), data, { revalidate: false });
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("board.saved") });
    } catch (err) {
      setError(apiError(err, t("worklog.error")));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsContentWrapper header={<BoardHeader />}>
      <PageHead title={t("board.settings_title")} />
      <form onSubmit={submit} className="w-full max-w-3xl space-y-8" data-mawesi="board-settings">
        <div className="border-b border-subtle pb-4">
          <h3 className="font-heading text-18 font-semibold">{t("board.settings_title")}</h3>
          <p className="text-13 text-secondary">{isAdmin ? t("board.settings_help") : t("fields.only_admins")}</p>
        </div>

        <section className="space-y-3">
          <div>
            <h4 className="text-14 font-medium">{t("board.columns")}</h4>
            <p className="text-13 text-secondary">{t("board.columns_help")}</p>
          </div>
          <div className="divide-y divide-subtle rounded-lg border border-subtle">
            {states.map((s) => {
              const l = limitOf(s.id);
              return (
                <div key={s.id} className="grid grid-cols-1 gap-2 p-3 sm:grid-cols-[10rem_7rem_1fr]" data-mawesi="board-column" data-state={s.name}>
                  <div className="flex items-center gap-2 text-13 font-medium">
                    <span className="size-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                    {s.name}
                  </div>
                  <label className="space-y-0.5">
                    <span className="block text-11 text-tertiary">{t("board.wip_limit")}</span>
                    <Input
                      name={`wip-${s.name}`}
                      type="number"
                      min={1}
                      max={999}
                      placeholder="—"
                      disabled={disabled}
                      value={l.wip_limit ?? ""}
                      onChange={(e) => setLimit(s.id, { wip_limit: e.target.value ? Number(e.target.value) : null })}
                      className="w-full"
                    />
                  </label>
                  <label className="space-y-0.5">
                    <span className="block text-11 text-tertiary">{t("board.dod")}</span>
                    <TextArea
                      name={`dod-${s.name}`}
                      rows={2}
                      disabled={disabled}
                      value={l.definition_of_done}
                      placeholder={t("board.dod_placeholder")}
                      onChange={(e) => setLimit(s.id, { definition_of_done: e.target.value })}
                      className="w-full text-13"
                    />
                  </label>
                </div>
              );
            })}
          </div>
        </section>

        <section className="space-y-3">
          <div>
            <h4 className="text-14 font-medium">{t("board.card_colors")}</h4>
            <p className="text-13 text-secondary">{t("board.card_colors_help")}</p>
          </div>
          {form.card_rules.length === 0 && <p className="text-13 text-tertiary">{t("board.no_rules")}</p>}
          {form.card_rules.map((r, i) => (
            <div key={i} className="space-y-3 rounded-lg border border-subtle p-3" data-mawesi="card-rule">
              <div className="flex flex-wrap items-end gap-2">
                <label className="min-w-48 flex-1 space-y-0.5">
                  <span className="block text-11 text-tertiary">{t("board.rule_name")}</span>
                  <Input name={`rule-name-${i}`} value={r.name} disabled={disabled} onChange={(e) => setRule(i, { name: e.target.value })} className="w-full" />
                </label>
                <label className="space-y-0.5">
                  <span className="flex items-center gap-1.5 text-11 text-tertiary">
                    {t("board.color")} <Swatch color={r.color} />
                  </span>
                  <select name={`rule-color-${i}`} className={selectClass} disabled={disabled} value={r.color} onChange={(e) => setRule(i, { color: e.target.value as TCardColor })}>
                    {CARD_COLORS.map((c) => (
                      <option key={c} value={c}>
                        {t(`board.color.${c}` as TKey)}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="flex h-8 items-center gap-1">
                  <Toggle value={r.enabled} disabled={disabled} label={t("auto.enabled")} onChange={(v) => setRule(i, { enabled: v })} />
                  {isAdmin && (
                    <>
                      <button type="button" disabled={i === 0} onClick={() => move(i, -1)} className="rounded p-1 hover:bg-layer-1 disabled:opacity-30" aria-label={t("board.up")}>
                        <ArrowUp className="size-3.5" />
                      </button>
                      <button type="button" disabled={i === form.card_rules.length - 1} onClick={() => move(i, 1)} className="rounded p-1 hover:bg-layer-1 disabled:opacity-30" aria-label={t("board.down")}>
                        <ArrowDown className="size-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setForm((f) => ({ ...f, card_rules: f.card_rules.filter((_, j) => j !== i) }))}
                        className="rounded p-1 hover:bg-layer-1"
                        aria-label={t("board.remove_rule")}
                        data-mawesi="card-rule-remove"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </>
                  )}
                </div>
              </div>
              <div className="space-y-2 text-13">
                <span className="block text-11 text-tertiary">{t("board.when")}</span>
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  <label className="flex items-center gap-1.5">
                    <input type="checkbox" name={`rule-overdue-${i}`} disabled={disabled} checked={!!r.conditions.overdue} onChange={(e) => setCond(i, { overdue: e.target.checked || undefined })} />
                    {t("board.cond_overdue")}
                  </label>
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      disabled={disabled}
                      checked={r.conditions.due_in_days !== undefined}
                      onChange={(e) => setCond(i, { due_in_days: e.target.checked ? 2 : undefined })}
                    />
                    {t("board.cond_due_in")}
                    <input
                      type="number"
                      name={`rule-due-${i}`}
                      min={0}
                      max={90}
                      disabled={disabled || r.conditions.due_in_days === undefined}
                      value={r.conditions.due_in_days ?? ""}
                      onChange={(e) => setCond(i, { due_in_days: Number(e.target.value) })}
                      className="h-6 w-12 rounded border border-subtle bg-surface-1 px-1"
                    />
                    {t("board.days")}
                  </label>
                  <label className="flex items-center gap-1.5">
                    <input type="checkbox" disabled={disabled} checked={!!r.conditions.unassigned} onChange={(e) => setCond(i, { unassigned: e.target.checked || undefined })} />
                    {t("board.cond_unassigned")}
                  </label>
                </div>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="text-11 text-tertiary">{t("board.cond_priority")}</span>
                  {PRIORITIES.map((p) => (
                    <label key={p} className="flex items-center gap-1">
                      <input
                        type="checkbox"
                        name={`rule-priority-${i}-${p}`}
                        disabled={disabled}
                        checked={!!r.conditions.priorities?.includes(p)}
                        onChange={(e) => setCond(i, { priorities: toggleIn(r.conditions.priorities, p, e.target.checked) })}
                      />
                      {t(`sla.priority.${p}` as TKey)}
                    </label>
                  ))}
                </div>
                {states.length > 0 && (
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="text-11 text-tertiary">{t("board.cond_column")}</span>
                    {states.map((s) => (
                      <label key={s.id} className="flex items-center gap-1">
                        <input
                          type="checkbox"
                          disabled={disabled}
                          checked={!!r.conditions.state_ids?.includes(s.id)}
                          onChange={(e) => setCond(i, { state_ids: toggleIn(r.conditions.state_ids, s.id, e.target.checked) })}
                        />
                        {s.name}
                      </label>
                    ))}
                  </div>
                )}
                {labels.length > 0 && (
                  <div className="flex max-h-24 flex-wrap items-center gap-x-3 gap-y-1 overflow-y-auto">
                    <span className="text-11 text-tertiary">{t("board.cond_label")}</span>
                    {labels.map((l) => (
                      <label key={l.id} className="flex items-center gap-1">
                        <input
                          type="checkbox"
                          disabled={disabled}
                          checked={!!r.conditions.label_ids?.includes(l.id)}
                          onChange={(e) => setCond(i, { label_ids: toggleIn(r.conditions.label_ids, l.id, e.target.checked) })}
                        />
                        {l.name}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {isAdmin && (
            <button
              type="button"
              onClick={() => setForm((f) => ({ ...f, card_rules: [...f.card_rules, newRule()] }))}
              className="flex items-center gap-1 rounded-md px-1 py-1 text-13 text-secondary hover:bg-layer-1 hover:text-primary"
              data-mawesi="card-rule-add"
            >
              <Plus className="size-3.5" />
              {t("board.add_rule")}
            </button>
          )}
        </section>

        <section className="space-y-3" data-mawesi="dependency-settings">
          <div>
            <h4 className="text-14 font-medium">{t("dep.settings")}</h4>
            <p className="text-13 text-secondary">{t("dep.settings_help")}</p>
          </div>
          {(["enforce", "auto_unblock", "reschedule"] as const).map((k) => (
            <div key={k} className="flex items-start gap-3">
              <Toggle
                value={(form.dependencies ?? DEPENDENCIES)[k]}
                disabled={disabled}
                label={t(`dep.${k}` as TKey)}
                onChange={(v) => setForm((f) => ({ ...f, dependencies: { ...(f.dependencies ?? DEPENDENCIES), [k]: v } }))}
              />
              <div className="text-13" data-mawesi={`dep-${k}`}>
                <div className="font-medium">{t(`dep.${k}` as TKey)}</div>
                <div className="text-secondary">{t(`dep.${k}_help` as TKey)}</div>
              </div>
            </div>
          ))}
        </section>

        {error && (
          <p className="text-13 text-danger-primary" role="alert">
            {error}
          </p>
        )}
        {isAdmin && (
          <Button type="submit" variant="primary" size="lg" loading={saving} data-mawesi="board-save">
            {saving ? t("worklog.saving") : t("worklog.save")}
          </Button>
        )}
      </form>
    </SettingsContentWrapper>
  );
});

export default BoardSettingsPage;
