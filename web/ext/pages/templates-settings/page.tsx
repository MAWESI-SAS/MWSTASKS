/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Configuración del proyecto → Plantillas: tareas con prioridad, lista, responsables, checklist y subtareas ya
 * armados. Crean admins y miembros; edita y borra quien la creó o un admin (mismas reglas que la API).
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR from "swr";
import { ArrowUp, LayoutTemplate, Pencil, Plus, Trash2, X } from "lucide-react";
import { groupModules } from "../../folders/group";
import { useT } from "../../i18n";
import type { TKey } from "../../i18n";
import {
  BreadcrumbLink, Breadcrumbs, Button, EUserPermissions, IconButton, Input, MemberDropdown, PageHead, SettingsContentWrapper,
  SettingsPageHeader, TextArea, TOAST_TYPE, setToast, useModule, useUser, useUserPermissions,
} from "../../plane";
import { PRIORITIES } from "../../sla/service";
import type { TPriority } from "../../sla/service";
import { templatesService, useTemplates } from "../../templates/service";
import type { TTemplate } from "../../templates/service";
import { MawesiConfirm } from "../../ui/confirm";

type TDraftSub = { name: string; priority: TPriority; checklist: string };
type TDraft = Omit<TTemplate, "checklist" | "subtasks"> & { checklist: string; subtasks: TDraftSub[] };

const EMPTY: TDraft = { name: "", priority: "none", module_id: null, assignee_ids: [], checklist: "", subtasks: [], add_parent_name: true };
const selectClass = "block h-9 w-full rounded-md border border-subtle bg-surface-1 px-2 text-13 text-primary";
const lines = (text: string) => text.split("\n").map((l) => l.trim()).filter(Boolean);

const toDraft = (x: TTemplate): TDraft => ({
  ...x,
  checklist: x.checklist.join("\n"),
  subtasks: x.subtasks.map((s) => ({ ...s, checklist: s.checklist.join("\n") })),
});

const fromDraft = (d: TDraft): TTemplate => ({
  ...d,
  name: d.name.trim(),
  checklist: lines(d.checklist),
  subtasks: d.subtasks.map((s) => ({ name: s.name.trim(), priority: s.priority, checklist: lines(s.checklist) })),
});

function TemplatesHeader() {
  const t = useT();
  return (
    <SettingsPageHeader
      leftItem={
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label={t("tpl.title")} icon={<LayoutTemplate className="size-4 text-tertiary" />} />} />
        </Breadcrumbs>
      }
    />
  );
}

const PrioritySelect = ({ value, onChange, name }: { value: TPriority; onChange: (p: TPriority) => void; name: string }) => {
  const t = useT();
  return (
    <select name={name} className={selectClass} value={value} onChange={(e) => onChange(e.target.value as TPriority)}>
      {PRIORITIES.map((p) => (
        <option key={p} value={p}>
          {t(`sla.priority.${p}` as TKey)}
        </option>
      ))}
    </select>
  );
};

const TemplatesSettingsPage = observer(function TemplatesSettingsPage() {
  const t = useT();
  const { workspaceSlug = "", projectId = "" } = useParams();
  const { data: currentUser } = useUser();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const role = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId);
  const isAdmin = role === EUserPermissions.ADMIN;
  const canCreate = isAdmin || role === EUserPermissions.MEMBER;
  const moduleStore = useModule();
  useSWR(workspaceSlug && projectId ? ["mawesi-tpl-modules", workspaceSlug, projectId] : null, () => moduleStore.fetchModules(workspaceSlug, projectId), {
    revalidateOnFocus: false,
  });
  const tree = groupModules(moduleStore.getProjectModuleDetails(projectId) ?? []);
  const { data: templates, mutate, isLoading } = useTemplates(workspaceSlug, projectId);
  const [editing, setEditing] = useState<{ id?: string; draft: TDraft } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toDelete, setToDelete] = useState<TTemplate | null>(null);
  const [deleting, setDeleting] = useState(false);

  const canEdit = (x: TTemplate) => isAdmin || (canCreate && !!currentUser?.id && x.created_by === currentUser.id);
  const draft = editing?.draft;
  const set = (patch: Partial<TDraft>) => editing && setEditing({ ...editing, draft: { ...editing.draft, ...patch } });
  const setSub = (i: number, patch: Partial<TDraftSub>) =>
    draft && set({ subtasks: draft.subtasks.map((s, j) => (j === i ? { ...s, ...patch } : s)) });
  const moveUp = (i: number) => {
    if (!draft || i === 0) return;
    const subs = [...draft.subtasks];
    [subs[i - 1], subs[i]] = [subs[i], subs[i - 1]];
    set({ subtasks: subs });
  };

  const open = (x?: TTemplate) => {
    setError(null);
    setEditing(x ? { id: x.id, draft: toDraft(x) } : { draft: EMPTY });
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    const body = fromDraft(editing.draft);
    if (!body.name) return setError(t("tpl.err_name"));
    if (body.subtasks.some((s) => !s.name)) return setError(t("tpl.err_subtask"));
    setSaving(true);
    setError(null);
    try {
      if (editing.id) await templatesService.update(workspaceSlug, projectId, editing.id, body);
      else await templatesService.create(workspaceSlug, projectId, body);
      await mutate();
      setEditing(null);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("tpl.saved") });
    } catch (err: unknown) {
      setError((err as { error?: string })?.error ?? t("worklog.error"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!toDelete?.id) return;
    setDeleting(true);
    try {
      await templatesService.remove(workspaceSlug, projectId, toDelete.id);
      await mutate();
      setToDelete(null);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("worklog.error") });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <SettingsContentWrapper header={<TemplatesHeader />}>
      <PageHead title={t("tpl.title")} />
      <div className="w-full max-w-2xl space-y-6" data-mawesi="templates-settings">
        <div className="flex items-start justify-between gap-4 border-b border-subtle pb-4">
          <div>
            <h3 className="font-heading text-18 font-semibold">{t("tpl.title")}</h3>
            <p className="text-13 text-secondary">{t("tpl.settings_help")}</p>
          </div>
          {canCreate && !editing && (
            <Button type="button" variant="primary" size="lg" prependIcon={<Plus />} onClick={() => open()} data-mawesi="template-new">
              {t("tpl.new")}
            </Button>
          )}
        </div>

        {!editing && (
          <ul className="space-y-2">
            {!isLoading && templates?.length === 0 && <li className="text-13 text-tertiary">{t("tpl.empty")}</li>}
            {templates?.map((x) => (
              <li key={x.id} className="flex items-center gap-3 rounded-md border border-subtle px-3 py-2" data-mawesi="template-row">
                <LayoutTemplate className="size-4 flex-shrink-0 text-tertiary" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-13 font-medium">{x.name}</div>
                  <div className="truncate text-11 text-tertiary">
                    {t("tpl.subtask_count").replace("{n}", String(x.subtasks.length))}
                    {x.subtasks.length > 0 && `: ${x.subtasks.map((s) => s.name).join(" · ")}`}
                  </div>
                </div>
                {canEdit(x) && (
                  <>
                    <IconButton type="button" variant="ghost" size="sm" icon={Pencil} onClick={() => open(x)} aria-label={t("tpl.edit")} data-mawesi="template-edit" />
                    <IconButton type="button" variant="ghost" size="sm" icon={Trash2} onClick={() => setToDelete(x)} aria-label={t("tpl.delete")} data-mawesi="template-delete" />
                  </>
                )}
              </li>
            ))}
          </ul>
        )}

        {editing && draft && (
          <form onSubmit={submit} className="space-y-5" data-mawesi="template-form">
            <label className="block space-y-1">
              <span className="text-13 text-secondary">{t("tpl.name")}</span>
              <Input name="name" value={draft.name} onChange={(e) => set({ name: e.target.value })} className="w-full" maxLength={120} autoFocus />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block space-y-1">
                <span className="text-13 text-secondary">{t("tpl.priority")}</span>
                <PrioritySelect name="priority" value={draft.priority} onChange={(priority) => set({ priority })} />
              </label>
              <label className="block space-y-1">
                <span className="text-13 text-secondary">{t("tpl.list")}</span>
                <select name="module" className={selectClass} value={draft.module_id ?? ""} onChange={(e) => set({ module_id: e.target.value || null })}>
                  <option value="">{t("tpl.no_list")}</option>
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
            </div>
            <div className="space-y-1">
              <span className="block text-13 text-secondary">{t("tpl.assignees")}</span>
              <div className="h-8" data-mawesi="template-assignees">
                <MemberDropdown
                  projectId={projectId}
                  value={draft.assignee_ids}
                  onChange={(ids: string[]) => set({ assignee_ids: ids })}
                  buttonVariant="border-with-text"
                  placeholder={t("tpl.assignees")}
                  multiple
                />
              </div>
            </div>
            <label className="block space-y-1">
              <span className="text-13 text-secondary">{t("tpl.checklist")}</span>
              <TextArea name="checklist" value={draft.checklist} onChange={(e) => set({ checklist: e.target.value })} className="min-h-20 w-full" />
            </label>

            <fieldset className="space-y-3">
              <legend className="text-13 text-secondary">{t("tpl.subtasks")}</legend>
              {draft.subtasks.map((s, i) => (
                <div key={i} className="space-y-2 rounded-md border border-subtle p-3" data-mawesi="template-subtask">
                  <div className="flex items-center gap-2">
                    <span className="w-5 text-right text-11 text-tertiary">{i + 1}.</span>
                    <Input name={`sub-name-${i}`} value={s.name} onChange={(e) => setSub(i, { name: e.target.value })} placeholder={t("tpl.subtask_name")} className="flex-1" maxLength={120} />
                    <div className="w-32">
                      <PrioritySelect name={`sub-priority-${i}`} value={s.priority} onChange={(priority) => setSub(i, { priority })} />
                    </div>
                    <IconButton type="button" variant="ghost" size="sm" icon={ArrowUp} disabled={i === 0} onClick={() => moveUp(i)} aria-label={t("tpl.up")} />
                    <IconButton type="button" variant="ghost" size="sm" icon={X} onClick={() => set({ subtasks: draft.subtasks.filter((_, j) => j !== i) })} aria-label={t("tpl.remove")} />
                  </div>
                  <TextArea name={`sub-checklist-${i}`} value={s.checklist} onChange={(e) => setSub(i, { checklist: e.target.value })} placeholder={t("tpl.subtask_checklist")} className="min-h-12 w-full text-13" />
                </div>
              ))}
              <Button
                type="button"
                variant="secondary"
                size="sm"
                prependIcon={<Plus />}
                onClick={() => set({ subtasks: [...draft.subtasks, { name: "", priority: "none", checklist: "" }] })}
                data-mawesi="template-add-subtask"
              >
                {t("tpl.add_subtask")}
              </Button>
              <label className="flex items-center gap-1.5 text-13">
                <input type="checkbox" name="add_parent_name" checked={draft.add_parent_name} onChange={(e) => set({ add_parent_name: e.target.checked })} />
                {t("tpl.add_parent_name")}
              </label>
            </fieldset>

            {error && (
              <p className="text-13 text-danger-primary" role="alert">
                {error}
              </p>
            )}
            <div className="flex gap-2">
              <Button type="submit" variant="primary" size="lg" loading={saving} data-mawesi="template-save">
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
        title={t("tpl.delete")}
        body={t("tpl.delete_body").replace("{name}", toDelete?.name ?? "")}
        confirmText={t("tpl.delete")}
        confirmingText={t("worklog.deleting")}
        cancelText={t("worklog.cancel")}
      />
    </SettingsContentWrapper>
  );
});

export default TemplatesSettingsPage;
