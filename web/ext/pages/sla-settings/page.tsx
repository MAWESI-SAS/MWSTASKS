/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Configuración del proyecto → SLA (solo admins editan): plazo por prioridad en horas hábiles, horario,
 * días hábiles, festivos de Colombia y a qué lista aplica.
 */
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR from "swr";
import { AlarmClock } from "lucide-react";
import { groupModules } from "../../folders/group";
import { useT } from "../../i18n";
import type { TKey } from "../../i18n";
import {
  BreadcrumbLink, Breadcrumbs, Button, EUserPermissions, Input, PageHead, SettingsContentWrapper, SettingsPageHeader,
  TOAST_TYPE, setToast, useModule, useUserPermissions,
} from "../../plane";
import { PRIORITIES, slaService } from "../../sla/service";
import type { TSlaPolicy } from "../../sla/service";
import { MawesiConfirm } from "../../ui/confirm";

const DEFAULT: TSlaPolicy = {
  module_id: null,
  hours: { urgent: 4, high: 8, medium: 16, low: 40, none: 40 },
  timezone: "America/Bogota",
  work_start: "08:00",
  work_end: "18:00",
  workdays: [0, 1, 2, 3, 4],
  colombia_holidays: true,
};
const DAYS = [0, 1, 2, 3, 4, 5, 6] as const;
const selectClass = "block h-9 w-full rounded-md border border-subtle bg-surface-1 px-2 text-13 text-primary disabled:opacity-60";

function SlaHeader() {
  const t = useT();
  return (
    <SettingsPageHeader
      leftItem={
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label={t("sla.settings_title")} icon={<AlarmClock className="size-4 text-tertiary" />} />} />
        </Breadcrumbs>
      }
    />
  );
}

const SlaSettingsPage = observer(function SlaSettingsPage() {
  const t = useT();
  const { workspaceSlug = "", projectId = "" } = useParams();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const isAdmin = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId) === EUserPermissions.ADMIN;
  const moduleStore = useModule();
  useSWR(workspaceSlug && projectId ? ["mawesi-sla-modules", workspaceSlug, projectId] : null, () => moduleStore.fetchModules(workspaceSlug, projectId), {
    revalidateOnFocus: false,
  });
  const tree = groupModules(moduleStore.getProjectModuleDetails(projectId) ?? []);
  const { data: saved, mutate, isLoading } = useSWR(
    workspaceSlug && projectId ? ["mawesi-sla-policy", workspaceSlug, projectId] : null,
    () => slaService.policy(workspaceSlug, projectId),
    { revalidateOnFocus: false }
  );
  const [form, setForm] = useState<TSlaPolicy>(DEFAULT);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    if (!isLoading) setForm(saved ?? DEFAULT);
  }, [saved, isLoading]);

  const disabled = !isAdmin || saving;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await mutate(await slaService.savePolicy(workspaceSlug, projectId, form), { revalidate: false });
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("sla.saved") });
    } catch (err: unknown) {
      setError((err as { error?: string })?.error ?? t("worklog.error"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    setRemoving(true);
    try {
      await slaService.removePolicy(workspaceSlug, projectId);
      await mutate(null, { revalidate: false });
      setConfirm(false);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("worklog.error") });
    } finally {
      setRemoving(false);
    }
  };

  return (
    <SettingsContentWrapper header={<SlaHeader />}>
      <PageHead title={t("sla.settings_title")} />
      <form onSubmit={submit} className="w-full max-w-2xl space-y-6" data-mawesi="sla-settings">
        <div className="border-b border-subtle pb-4">
          <h3 className="font-heading text-18 font-semibold">{t("sla.settings_title")}</h3>
          <p className="text-13 text-secondary">{isAdmin ? t("sla.settings_help") : t("fields.only_admins")}</p>
          {!isLoading && !saved && <p className="mt-1 text-13 text-warning-primary">{t("sla.off")}</p>}
        </div>

        <label className="block space-y-1">
          <span className="text-13 text-secondary">{t("sla.applies_to")}</span>
          <select name="module" className={selectClass} disabled={disabled} value={form.module_id ?? ""} onChange={(e) => setForm({ ...form, module_id: e.target.value || null })}>
            <option value="">{t("sla.all_items")}</option>
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

        <fieldset className="space-y-2">
          <legend className="text-13 text-secondary">{t("sla.hours_by_priority")}</legend>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {PRIORITIES.map((p) => (
              <label key={p} className="space-y-1">
                <span className="block text-11 text-tertiary">{t(`sla.priority.${p}` as TKey)}</span>
                <Input
                  name={`hours-${p}`}
                  type="number"
                  min={0.25}
                  step={0.25}
                  disabled={disabled}
                  value={String(form.hours[p])}
                  onChange={(e) => setForm({ ...form, hours: { ...form.hours, [p]: Number(e.target.value) } })}
                  className="w-full"
                />
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="text-13 text-secondary">{t("sla.schedule")}</legend>
          <div className="flex flex-wrap items-end gap-3">
            <label className="space-y-1">
              <span className="block text-11 text-tertiary">{t("sla.from")}</span>
              <Input name="work_start" type="time" disabled={disabled} value={form.work_start} onChange={(e) => setForm({ ...form, work_start: e.target.value })} />
            </label>
            <label className="space-y-1">
              <span className="block text-11 text-tertiary">{t("sla.to")}</span>
              <Input name="work_end" type="time" disabled={disabled} value={form.work_end} onChange={(e) => setForm({ ...form, work_end: e.target.value })} />
            </label>
            <span className="pb-2 text-11 text-tertiary">{form.timezone}</span>
          </div>
          <div className="flex flex-wrap gap-3">
            {DAYS.map((d) => (
              <label key={d} className="flex items-center gap-1.5 text-13">
                <input
                  type="checkbox"
                  name={`day-${d}`}
                  disabled={disabled}
                  checked={form.workdays.includes(d)}
                  onChange={(e) =>
                    setForm({ ...form, workdays: e.target.checked ? [...form.workdays, d].sort() : form.workdays.filter((x) => x !== d) })
                  }
                />
                {t(`sla.day.${d}` as TKey)}
              </label>
            ))}
          </div>
          <label className="flex items-center gap-1.5 text-13">
            <input
              type="checkbox"
              name="colombia_holidays"
              disabled={disabled}
              checked={form.colombia_holidays}
              onChange={(e) => setForm({ ...form, colombia_holidays: e.target.checked })}
            />
            {t("sla.holidays")}
          </label>
        </fieldset>

        <p className="text-11 text-tertiary">{t("sla.clock_help")}</p>
        {error && (
          <p className="text-13 text-danger-primary" role="alert">
            {error}
          </p>
        )}
        {isAdmin && (
          <div className="flex gap-2">
            <Button type="submit" variant="primary" size="lg" loading={saving} data-mawesi="sla-save">
              {saving ? t("worklog.saving") : t("worklog.save")}
            </Button>
            {saved && (
              <Button type="button" variant="secondary" size="lg" onClick={() => setConfirm(true)} data-mawesi="sla-remove">
                {t("sla.turn_off")}
              </Button>
            )}
          </div>
        )}
      </form>
      <MawesiConfirm
        isOpen={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={remove}
        isSubmitting={removing}
        title={t("sla.turn_off")}
        body={t("sla.turn_off_body")}
        confirmText={t("sla.turn_off")}
        confirmingText={t("worklog.deleting")}
        cancelText={t("worklog.cancel")}
      />
    </SettingsContentWrapper>
  );
});

export default SlaSettingsPage;
