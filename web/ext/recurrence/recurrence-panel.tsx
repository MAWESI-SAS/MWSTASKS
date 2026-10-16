/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Panel "Repetir" del detalle de la tarea: muestra cada cuánto se repite y cuándo se crea la siguiente, y permite
 * configurarlo o quitarlo. La siguiente la crea el servidor (plane_mawesi/recurrence.py, cada minuto).
 */
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { Repeat } from "lucide-react";
import { useT } from "../i18n";
import type { TKey } from "../i18n";
import { Button, Input, TOAST_TYPE, setToast, useIssueDetail } from "../plane";
import { MawesiModal } from "../ui/modal";
import { FREQUENCIES, recurrenceService } from "./service";
import type { TRecurrence, TRecurrenceInput } from "./service";

type Props = { workspaceSlug: string; projectId: string; issueId: string; disabled?: boolean };

const selectClass = "w-full rounded-md border border-subtle bg-surface-1 px-2 py-1.5 text-13";

const formatDay = (iso: string | null, locale: string) => {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(locale, { weekday: "short", day: "numeric", month: "short" });
};

const summary = (r: TRecurrenceInput, t: ReturnType<typeof useT>) =>
  r.interval === 1 ? t(`rec.every.${r.frequency}` as TKey) : t(`rec.every_n.${r.frequency}` as TKey).replace("{n}", String(r.interval));

export const RecurrencePanel = observer(function RecurrencePanel({ workspaceSlug, projectId, issueId, disabled }: Props) {
  const t = useT();
  const { issue } = useIssueDetail();
  const current = issue.getIssueById(issueId);
  // Se relee al cambiar estado o fechas: la próxima fecha y la ocurrencia vigente dependen de eso.
  const version = `${current?.state_id ?? ""}|${current?.target_date ?? ""}|${current?.start_date ?? ""}`;
  const key = workspaceSlug && projectId && issueId ? ["mawesi-recurrence", workspaceSlug, projectId, issueId, version] : null;
  const { data, mutate, isLoading } = useSWR(key, () => recurrenceService.read(workspaceSlug, projectId, issueId), { revalidateOnFocus: false });
  const [open, setOpen] = useState(false);
  const locale = t("rec.locale");

  if (isLoading || (!data && disabled)) return null;
  return (
    <div data-mawesi="recurrence-panel" className="space-y-2">
      <h5 className="text-body-xs-medium">{t("rec.title")}</h5>
      {data ? (
        <div className="flex items-start gap-2 rounded-md border-[0.5px] border-subtle px-2 py-1.5 text-13" data-mawesi="recurrence-summary">
          <Repeat className="mt-0.5 size-3.5 flex-shrink-0 text-tertiary" />
          <div className="min-w-0 flex-1">
            <div className="font-medium">{summary(data, t)}</div>
            <div className="text-11 text-secondary">
              {t(`rec.trigger.${data.trigger}` as TKey)}
              {data.next_target && ` · ${t("rec.next_due")}: ${formatDay(data.next_target, locale)}`}
            </div>
          </div>
          {!disabled && (
            <button type="button" className="text-11 text-accent-primary hover:underline" onClick={() => setOpen(true)} data-mawesi="recurrence-edit">
              {t("tpl.edit")}
            </button>
          )}
        </div>
      ) : (
        <Button type="button" variant="secondary" size="sm" prependIcon={<Repeat />} onClick={() => setOpen(true)} data-mawesi="recurrence-set">
          {t("rec.set")}
        </Button>
      )}
      <RecurrenceDialog
        isOpen={open}
        onClose={() => setOpen(false)}
        value={data ?? null}
        hasDueDate={!!current?.target_date}
        onSave={async (input) => {
          await mutate(await recurrenceService.write(workspaceSlug, projectId, issueId, input), { revalidate: false });
          setToast({ type: TOAST_TYPE.SUCCESS, title: t("rec.saved") });
        }}
        onRemove={async () => {
          await recurrenceService.remove(workspaceSlug, projectId, issueId);
          await mutate(null, { revalidate: false });
        }}
      />
    </div>
  );
});

type DialogProps = {
  isOpen: boolean;
  onClose: () => void;
  value: TRecurrence | null;
  hasDueDate: boolean;
  onSave: (input: TRecurrenceInput) => Promise<void>;
  onRemove: () => Promise<void>;
};

function RecurrenceDialog({ isOpen, onClose, value, hasDueDate, onSave, onRemove }: DialogProps) {
  const t = useT();
  const [form, setForm] = useState<TRecurrenceInput>({ frequency: "weekly", interval: 1, trigger: "complete" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setForm(value ? { frequency: value.frequency, interval: value.interval, trigger: value.trigger } : { frequency: "weekly", interval: 1, trigger: "complete" });
    setError(null);
  }, [isOpen, value]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      onClose();
    } catch (err: unknown) {
      setError((err as { error?: string })?.error ?? t("worklog.error"));
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!Number.isInteger(form.interval) || form.interval < 1 || form.interval > 30) return setError(t("rec.err_interval"));
    void run(() => onSave(form));
  };

  return (
    <MawesiModal isOpen={isOpen} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4 px-5 py-4" data-mawesi="recurrence-dialog">
        <h3 className="text-18 font-medium">{t("rec.title")}</h3>
        <div className="grid grid-cols-[6rem_1fr] items-end gap-3">
          <label className="block space-y-1">
            <span className="text-13 text-secondary">{t("rec.every_label")}</span>
            <Input name="interval" type="number" min={1} max={30} value={String(form.interval)} onChange={(e) => setForm({ ...form, interval: Number(e.target.value) })} className="w-full" />
          </label>
          <label className="block space-y-1">
            <span className="text-13 text-secondary">{t("rec.unit_label")}</span>
            <select name="frequency" value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value as TRecurrenceInput["frequency"] })} className={selectClass}>
              {FREQUENCIES.map((f) => (
                <option key={f} value={f}>
                  {t(`rec.unit.${f}` as TKey)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <fieldset className="space-y-1.5">
          <legend className="text-13 text-secondary">{t("rec.when")}</legend>
          {(["complete", "schedule"] as const).map((tr) => (
            <label key={tr} className="flex items-start gap-2 text-13">
              <input
                type="radio"
                name="trigger"
                value={tr}
                className="mt-0.5"
                checked={form.trigger === tr}
                disabled={tr === "schedule" && !hasDueDate}
                onChange={() => setForm({ ...form, trigger: tr })}
              />
              <span>
                {t(`rec.trigger.${tr}` as TKey)}
                {tr === "schedule" && !hasDueDate && <span className="block text-11 text-tertiary">{t("rec.needs_due")}</span>}
              </span>
            </label>
          ))}
        </fieldset>
        <p className="text-11 text-tertiary">{t("rec.help")}</p>
        {error && (
          <p className="text-13 text-danger-primary" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-between gap-2">
          <div>
            {value && (
              <Button type="button" variant="secondary" size="lg" onClick={() => void run(onRemove)} disabled={busy} data-mawesi="recurrence-remove">
                {t("rec.remove")}
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="secondary" size="lg" onClick={onClose}>
              {t("worklog.cancel")}
            </Button>
            <Button type="submit" variant="primary" size="lg" loading={busy} data-mawesi="recurrence-save">
              {busy ? t("worklog.saving") : t("worklog.save")}
            </Button>
          </div>
        </div>
      </form>
    </MawesiModal>
  );
}
