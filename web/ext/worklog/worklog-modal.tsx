/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useT } from "../i18n";
import { Button, Input, TOAST_TYPE, TextArea, setToast } from "../plane";
import { MawesiModal } from "../ui/modal";
import { MAX_MINUTES, formatMinutes, parseDuration, todayISO } from "./format";
import { worklogService } from "./service";
import type { TWorklog } from "./service";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => Promise<void>;
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  entry?: TWorklog;
};

export function WorklogModal({ isOpen, onClose, onSaved, workspaceSlug, projectId, issueId, entry }: Props) {
  const t = useT();
  const [duration, setDuration] = useState("");
  const [date, setDate] = useState(todayISO());
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setDuration(entry ? formatMinutes(entry.duration_minutes).replace(" min", "m").replace(" h", "h") : "");
    setDate(entry?.date ?? todayISO());
    setNote(entry?.description ?? "");
    setError(null);
  }, [isOpen, entry]);

  const minutes = parseDuration(duration);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!minutes || minutes < 1 || minutes > MAX_MINUTES) return setError(t("worklog.err_duration"));
    if (date > todayISO()) return setError(t("worklog.err_date"));
    setSaving(true);
    try {
      const data = { duration_minutes: minutes, date, description: note.trim() };
      if (entry) await worklogService.update(workspaceSlug, projectId, issueId, entry.id, data);
      else await worklogService.create(workspaceSlug, projectId, issueId, data);
      await onSaved();
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("worklog.saved") });
      onClose();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("worklog.error") });
    } finally {
      setSaving(false);
    }
  };

  return (
    <MawesiModal isOpen={isOpen} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4 px-5 py-4" data-mawesi="worklog-modal">
        <h3 className="text-18 font-medium">{entry ? t("worklog.edit") : t("worklog.log")}</h3>
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1">
            <span className="text-13 text-secondary">{t("worklog.duration")}</span>
            <Input
              name="duration"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              placeholder="1h 30m"
              autoFocus
              className="w-full"
              hasError={!!error && !minutes}
            />
            <span className="block text-11 text-tertiary">
              {minutes ? `= ${formatMinutes(minutes)}` : t("worklog.duration_hint")}
            </span>
          </label>
          <label className="space-y-1">
            <span className="text-13 text-secondary">{t("worklog.date")}</span>
            <Input name="date" type="date" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} className="w-full" />
          </label>
        </div>
        <label className="block space-y-1">
          <span className="text-13 text-secondary">{t("worklog.note")}</span>
          <TextArea name="note" value={note} onChange={(e) => setNote(e.target.value)} rows={3} className="w-full" />
        </label>
        {error && <p className="text-13 text-danger-primary" role="alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="lg" onClick={onClose}>
            {t("worklog.cancel")}
          </Button>
          <Button type="submit" variant="primary" size="lg" loading={saving}>
            {saving ? t("worklog.saving") : t("worklog.save")}
          </Button>
        </div>
      </form>
    </MawesiModal>
  );
}
