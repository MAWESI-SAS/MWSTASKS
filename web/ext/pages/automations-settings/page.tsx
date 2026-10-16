/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Configuración del proyecto → Reglas: "Cuando <algo pasa> → <acciones>" (como las automatizaciones de ClickUp).
 * Solo admins crean, cambian, apagan y borran; los miembros las ven. Las corre el servidor (automations.py).
 */
import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR from "swr";
import { Pencil, Plus, Trash2, Zap } from "lucide-react";
import { automationsService } from "../../automations/service";
import type { TActions, TRule, TRulesData, TTrigger } from "../../automations/service";
import { TRIGGERS } from "../../automations/service";
import { groupModules } from "../../folders/group";
import { useT } from "../../i18n";
import type { TKey } from "../../i18n";
import {
  BreadcrumbLink, Breadcrumbs, Button, EUserPermissions, IconButton, Input, MemberDropdown, PageHead, SettingsContentWrapper,
  SettingsPageHeader, TOAST_TYPE, setToast, useMember, useModule, useUserPermissions,
} from "../../plane";
import { PRIORITIES } from "../../sla/service";
import type { TPriority } from "../../sla/service";
import { MawesiConfirm } from "../../ui/confirm";

type TActionKey = keyof TActions;
const ACTION_KEYS: TActionKey[] = ["assignee_ids", "state_id", "priority", "label_ids", "due_in_days", "template_id"];
const EMPTY: TRule = { name: "", enabled: true, trigger: "priority", trigger_value: "urgent", module_id: null, actions: {} };
const selectClass = "block h-9 w-full rounded-md border border-subtle bg-surface-1 px-2 text-13 text-primary";

function RulesHeader() {
  const t = useT();
  return (
    <SettingsPageHeader
      leftItem={
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label={t("auto.title")} icon={<Zap className="size-4 text-tertiary" />} />} />
        </Breadcrumbs>
      }
    />
  );
}

const AutomationsSettingsPage = observer(function AutomationsSettingsPage() {
  const t = useT();
  const { workspaceSlug = "", projectId = "" } = useParams();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const isAdmin = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId) === EUserPermissions.ADMIN;
  const { getUserDetails } = useMember();
  const moduleStore = useModule();
  useSWR(workspaceSlug && projectId ? ["mawesi-auto-modules", workspaceSlug, projectId] : null, () => moduleStore.fetchModules(workspaceSlug, projectId), {
    revalidateOnFocus: false,
  });
  const modules = moduleStore.getProjectModuleDetails(projectId) ?? [];
  const tree = groupModules(modules);
  const { data, mutate, isLoading } = useSWR(
    workspaceSlug && projectId ? ["mawesi-automations", workspaceSlug, projectId] : null,
    () => automationsService.list(workspaceSlug, projectId),
    { revalidateOnFocus: false }
  );
  const [editing, setEditing] = useState<TRule | null>(null);
  const [on, setOn] = useState<Partial<Record<TActionKey, boolean>>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toDelete, setToDelete] = useState<TRule | null>(null);
  const [deleting, setDeleting] = useState(false);

  const nameOf = (list: { id: string; name: string }[] | undefined, id?: string | null) => list?.find((x) => x.id === id)?.name ?? "—";
  const moduleName = (id?: string | null) => nameOf(modules.map((m) => ({ id: m.id, name: m.name })), id);
  const priorityName = (p?: string) => (p ? t(`sla.priority.${p}` as TKey) : "—");

  /** "Cuando la prioridad cambia a Urgente (en Incidentes) → asignar a Ana · vence en 1 día hábil" */
  const describe = (r: TRule, d: TRulesData) => {
    const value = {
      created: "",
      added_to_list: moduleName(r.trigger_value),
      state: nameOf(d.states, r.trigger_value),
      priority: priorityName(r.trigger_value),
    }[r.trigger];
    const when = `${t(`auto.when.${r.trigger}` as TKey)}${value ? ` ${value}` : ""}${r.module_id ? ` (${t("auto.in_list")} ${moduleName(r.module_id)})` : ""}`;
    const a = r.actions;
    const parts = [
      a.assignee_ids?.length && `${t("auto.do.assignee_ids")} ${a.assignee_ids.map((id) => getUserDetails(id)?.display_name ?? "?").join(", ")}`,
      a.state_id && `${t("auto.do.state_id")} ${nameOf(d.states, a.state_id)}`,
      a.priority && `${t("auto.do.priority")} ${priorityName(a.priority)}`,
      a.label_ids?.length && `${t("auto.do.label_ids")} ${a.label_ids.map((id) => nameOf(d.labels, id)).join(", ")}`,
      a.due_in_days !== undefined && (a.due_in_days === 0 ? t("auto.do_due_today") : t("auto.do_due").replace("{n}", String(a.due_in_days))),
      a.template_id && `${t("auto.do.template_id")} ${nameOf(d.templates, a.template_id)}`,
    ].filter(Boolean);
    return `${when} → ${parts.join(" · ")}`;
  };

  const open = (r?: TRule) => {
    setError(null);
    const rule = r ?? EMPTY;
    setEditing({ ...rule, actions: { ...rule.actions } });
    setOn(Object.fromEntries(ACTION_KEYS.map((k) => [k, rule.actions[k] !== undefined])));
  };
  const set = (patch: Partial<TRule>) => editing && setEditing({ ...editing, ...patch });
  const setAction = (patch: Partial<TActions>) => editing && setEditing({ ...editing, actions: { ...editing.actions, ...patch } });

  const changeTrigger = (trigger: TTrigger) => {
    const first = { created: "", added_to_list: modules[0]?.id ?? "", state: data?.states[0]?.id ?? "", priority: "urgent" }[trigger];
    set({ trigger, trigger_value: first, module_id: trigger === "state" || trigger === "priority" ? editing?.module_id ?? null : null });
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    const actions = Object.fromEntries(ACTION_KEYS.filter((k) => on[k]).map((k) => [k, editing.actions[k] ?? (k === "due_in_days" ? 0 : undefined)]));
    const body = { ...editing, name: editing.name.trim(), actions: actions as TActions };
    if (!body.name) return setError(t("auto.err_name"));
    if (Object.keys(actions).length === 0) return setError(t("auto.err_action"));
    setSaving(true);
    setError(null);
    try {
      if (editing.id) await automationsService.update(workspaceSlug, projectId, editing.id, body);
      else await automationsService.create(workspaceSlug, projectId, body);
      await mutate();
      setEditing(null);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("auto.saved") });
    } catch (err: unknown) {
      setError((err as { error?: string })?.error ?? t("worklog.error"));
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (r: TRule) => {
    try {
      await automationsService.update(workspaceSlug, projectId, r.id!, { enabled: !r.enabled });
      await mutate();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("worklog.error") });
    }
  };

  const remove = async () => {
    if (!toDelete?.id) return;
    setDeleting(true);
    try {
      await automationsService.remove(workspaceSlug, projectId, toDelete.id);
      await mutate();
      setToDelete(null);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("worklog.error") });
    } finally {
      setDeleting(false);
    }
  };

  const moduleOptions = (
    <>
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
    </>
  );
  const priorityOptions = PRIORITIES.map((p: TPriority) => (
    <option key={p} value={p}>
      {priorityName(p)}
    </option>
  ));

  const actionRow = (k: TActionKey, control: ReactNode) => (
    <div key={k} className="flex flex-wrap items-center gap-3" data-mawesi={`auto-action-${k}`}>
      <label className="flex w-48 items-center gap-1.5 text-13">
        <input type="checkbox" name={`on-${k}`} checked={!!on[k]} onChange={(e) => setOn({ ...on, [k]: e.target.checked })} />
        {k === "due_in_days" ? t("auto.do_due_label") : t(`auto.do.${k}` as TKey)}
      </label>
      {on[k] && <div className="min-w-48 flex-1">{control}</div>}
    </div>
  );

  return (
    <SettingsContentWrapper header={<RulesHeader />}>
      <PageHead title={t("auto.title")} />
      <div className="w-full max-w-2xl space-y-6" data-mawesi="automations-settings">
        <div className="flex items-start justify-between gap-4 border-b border-subtle pb-4">
          <div>
            <h3 className="font-heading text-18 font-semibold">{t("auto.title")}</h3>
            <p className="text-13 text-secondary">{isAdmin ? t("auto.help") : t("fields.only_admins")}</p>
          </div>
          {isAdmin && !editing && (
            <Button type="button" variant="primary" size="lg" prependIcon={<Plus />} onClick={() => open()} data-mawesi="auto-new">
              {t("auto.new")}
            </Button>
          )}
        </div>

        {!editing && data && (
          <ul className="space-y-2">
            {!isLoading && data.rules.length === 0 && <li className="text-13 text-tertiary">{t("auto.empty")}</li>}
            {data.rules.map((r) => (
              <li key={r.id} className={`flex items-center gap-3 rounded-md border border-subtle px-3 py-2 ${r.enabled ? "" : "opacity-60"}`} data-mawesi="auto-row">
                <Zap className="size-4 flex-shrink-0 text-tertiary" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-13 font-medium">{r.name}</div>
                  <div className="text-11 text-tertiary">{describe(r, data)}</div>
                  <div className="text-11 text-tertiary">{t("auto.runs").replace("{n}", String(r.runs ?? 0))}</div>
                </div>
                {isAdmin && (
                  <>
                    <label className="flex items-center gap-1 text-11 text-secondary">
                      <input type="checkbox" checked={r.enabled} onChange={() => void toggle(r)} data-mawesi="auto-toggle" />
                      {t("auto.enabled")}
                    </label>
                    <IconButton type="button" variant="ghost" size="sm" icon={Pencil} onClick={() => open(r)} aria-label={t("tpl.edit")} data-mawesi="auto-edit" />
                    <IconButton type="button" variant="ghost" size="sm" icon={Trash2} onClick={() => setToDelete(r)} aria-label={t("auto.delete")} data-mawesi="auto-delete" />
                  </>
                )}
              </li>
            ))}
          </ul>
        )}

        {editing && data && (
          <form onSubmit={submit} className="space-y-5" data-mawesi="auto-form">
            <label className="block space-y-1">
              <span className="text-13 text-secondary">{t("auto.name")}</span>
              <Input name="name" value={editing.name} onChange={(e) => set({ name: e.target.value })} className="w-full" maxLength={120} autoFocus />
            </label>

            <fieldset className="space-y-2">
              <legend className="text-13 font-medium">{t("auto.when_title")}</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <select name="trigger" className={selectClass} value={editing.trigger} onChange={(e) => changeTrigger(e.target.value as TTrigger)}>
                  {TRIGGERS.map((tr) => (
                    <option key={tr} value={tr}>
                      {t(`auto.when.${tr}` as TKey)}
                    </option>
                  ))}
                </select>
                {editing.trigger !== "created" && (
                  <select name="trigger_value" className={selectClass} value={editing.trigger_value} onChange={(e) => set({ trigger_value: e.target.value })}>
                    {editing.trigger === "added_to_list" && moduleOptions}
                    {editing.trigger === "state" &&
                      data.states.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    {editing.trigger === "priority" && priorityOptions}
                  </select>
                )}
              </div>
              {(editing.trigger === "state" || editing.trigger === "priority") && (
                <label className="block space-y-1">
                  <span className="text-11 text-tertiary">{t("auto.only_list")}</span>
                  <select name="module" className={selectClass} value={editing.module_id ?? ""} onChange={(e) => set({ module_id: e.target.value || null })}>
                    <option value="">{t("auto.any_list")}</option>
                    {moduleOptions}
                  </select>
                </label>
              )}
              {editing.trigger === "created" && <p className="text-11 text-tertiary">{t("auto.created_help")}</p>}
            </fieldset>

            <fieldset className="space-y-3">
              <legend className="text-13 font-medium">{t("auto.then_title")}</legend>
              {actionRow(
                "assignee_ids",
                <div className="h-8">
                  <MemberDropdown
                    projectId={projectId}
                    value={editing.actions.assignee_ids ?? []}
                    onChange={(ids: string[]) => setAction({ assignee_ids: ids })}
                    buttonVariant="border-with-text"
                    placeholder={t("tpl.assignees")}
                    multiple
                  />
                </div>
              )}
              {actionRow(
                "state_id",
                <select name="action-state" className={selectClass} value={editing.actions.state_id ?? ""} onChange={(e) => setAction({ state_id: e.target.value })}>
                  <option value="" disabled>
                    —
                  </option>
                  {data.states.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              )}
              {actionRow(
                "priority",
                <select name="action-priority" className={selectClass} value={editing.actions.priority ?? ""} onChange={(e) => setAction({ priority: e.target.value as TPriority })}>
                  <option value="" disabled>
                    —
                  </option>
                  {priorityOptions}
                </select>
              )}
              {actionRow(
                "label_ids",
                <div className="flex max-h-32 flex-wrap gap-x-3 gap-y-1 overflow-y-auto rounded-md border border-subtle p-2">
                  {data.labels.length === 0 && <span className="text-11 text-tertiary">{t("auto.no_labels")}</span>}
                  {data.labels.map((l) => (
                    <label key={l.id} className="flex items-center gap-1 text-13">
                      <input
                        type="checkbox"
                        checked={editing.actions.label_ids?.includes(l.id) ?? false}
                        onChange={(e) => {
                          const cur = editing.actions.label_ids ?? [];
                          setAction({ label_ids: e.target.checked ? [...cur, l.id] : cur.filter((x) => x !== l.id) });
                        }}
                      />
                      {l.name}
                    </label>
                  ))}
                </div>
              )}
              {actionRow(
                "due_in_days",
                <div className="flex items-center gap-2 text-13">
                  <Input
                    name="action-due"
                    type="number"
                    min={0}
                    max={365}
                    value={String(editing.actions.due_in_days ?? 0)}
                    onChange={(e) => setAction({ due_in_days: Number(e.target.value) })}
                    className="w-20"
                  />
                  {t("auto.business_days")}
                </div>
              )}
              {actionRow(
                "template_id",
                data.templates.length === 0 ? (
                  <span className="text-11 text-tertiary">{t("tpl.none_yet")}</span>
                ) : (
                  <select name="action-template" className={selectClass} value={editing.actions.template_id ?? ""} onChange={(e) => setAction({ template_id: e.target.value })}>
                    <option value="" disabled>
                      —
                    </option>
                    {data.templates.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.name}
                      </option>
                    ))}
                  </select>
                )
              )}
            </fieldset>
            <p className="text-11 text-tertiary">{t("auto.form_help")}</p>

            {error && (
              <p className="text-13 text-danger-primary" role="alert">
                {error}
              </p>
            )}
            <div className="flex gap-2">
              <Button type="submit" variant="primary" size="lg" loading={saving} data-mawesi="auto-save">
                {saving ? t("worklog.saving") : t("worklog.save")}
              </Button>
              <Button type="button" variant="secondary" size="lg" onClick={() => setEditing(null)}>
                {t("worklog.cancel")}
              </Button>
            </div>
          </form>
        )}
      </div>
      <MawesiConfirm
        isOpen={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={remove}
        isSubmitting={deleting}
        title={t("auto.delete")}
        body={t("auto.delete_body").replace("{name}", toDelete?.name ?? "")}
        confirmText={t("auto.delete")}
        confirmingText={t("worklog.deleting")}
        cancelText={t("worklog.cancel")}
      />
    </SettingsContentWrapper>
  );
});

export default AutomationsSettingsPage;
