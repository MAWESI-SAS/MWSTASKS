/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { useState } from "react";
import { observer } from "mobx-react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useT } from "../i18n";
import { ButtonAvatars, TOAST_TYPE, setToast, useMember } from "../plane";
import { MawesiConfirm } from "../ui/confirm";
import { formatMinutes } from "./format";
import { worklogService } from "./service";
import type { TWorklog } from "./service";
import { useWorklogPermissions, useWorklogs } from "./use-worklogs";
import { WorklogModal } from "./worklog-modal";

type Props = { workspaceSlug: string; projectId: string; issueId: string; disabled?: boolean };

export const WorklogPanel = observer(function WorklogPanel({ workspaceSlug, projectId, issueId, disabled }: Props) {
  const t = useT();
  const { entries, total, refresh } = useWorklogs(workspaceSlug, projectId, issueId);
  const { canWrite, canEdit } = useWorklogPermissions(workspaceSlug, projectId);
  const { getUserDetails } = useMember();
  const [modal, setModal] = useState<{ open: boolean; entry?: TWorklog }>({ open: false });
  const [toDelete, setToDelete] = useState<TWorklog | null>(null);
  const [deleting, setDeleting] = useState(false);

  if (!canWrite) return null; // guests: las horas no se muestran

  const confirmDelete = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await worklogService.remove(workspaceSlug, projectId, issueId, toDelete.id);
      await refresh();
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("worklog.deleted") });
      setToDelete(null);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("worklog.error") });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div data-mawesi="worklog-panel" className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h5 className="text-body-xs-medium">{t("worklog.title")}</h5>
        <span className="text-13 font-medium" data-mawesi="worklog-total">
          {t("worklog.total")}: {formatMinutes(total)}
        </span>
      </div>
      {entries.length === 0 ? (
        <p className="text-13 text-tertiary">{t("worklog.empty")}</p>
      ) : (
        <ul className="max-h-48 space-y-1 overflow-y-auto">
          {entries.map((e) => (
            <li key={e.id} className="group flex items-start gap-2 rounded-md px-1 py-1 hover:bg-layer-1" data-mawesi="worklog-entry">
              <ButtonAvatars showTooltip userIds={e.member} size="sm" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-13">
                  <span className="font-medium">{formatMinutes(e.duration_minutes)}</span>
                  <span className="text-tertiary">{e.date}</span>
                  <span className="truncate text-tertiary">{getUserDetails(e.member)?.display_name}</span>
                </div>
                {e.description && <p className="truncate text-11 text-secondary" title={e.description}>{e.description}</p>}
              </div>
              {!disabled && canEdit(e) && (
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100">
                  <button type="button" data-mawesi="worklog-edit" aria-label={t("worklog.edit")} onClick={() => setModal({ open: true, entry: e })} className="rounded p-1 hover:bg-layer-2">
                    <Pencil className="h-3 w-3" />
                  </button>
                  <button type="button" data-mawesi="worklog-delete" aria-label={t("worklog.delete")} onClick={() => setToDelete(e)} className="rounded p-1 hover:bg-layer-2">
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {!disabled && (
        <button
          type="button"
          onClick={() => setModal({ open: true })}
          className="flex items-center gap-1 rounded-md px-1 py-1 text-13 text-secondary hover:bg-layer-1 hover:text-primary"
          data-mawesi="worklog-add"
        >
          <Plus className="h-3.5 w-3.5" />
          {t("worklog.log")}
        </button>
      )}
      <WorklogModal
        isOpen={modal.open}
        entry={modal.entry}
        onClose={() => setModal((m) => ({ ...m, open: false }))}
        onSaved={refresh}
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        issueId={issueId}
      />
      <MawesiConfirm
        isOpen={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={confirmDelete}
        isSubmitting={deleting}
        title={t("worklog.delete_title")}
        body={t("worklog.delete_body")}
        confirmText={t("worklog.delete")}
        confirmingText={t("worklog.deleting")}
        cancelText={t("worklog.cancel")}
      />
    </div>
  );
});
