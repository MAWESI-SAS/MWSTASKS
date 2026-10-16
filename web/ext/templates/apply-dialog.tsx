/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Ventana "usar plantilla". Dos casos:
 * - Desde una lista del árbol (o el "+"): crea la tarea con su checklist y sus subtareas, y la abre.
 * - Desde el detalle de una tarea: le agrega las subtareas de la plantilla (la descripción no se toca).
 */
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { observer } from "mobx-react";
import { Link, useNavigate } from "react-router";
import { useT } from "../i18n";
import { Button, Input, TOAST_TYPE, setToast, useIssueDetail, useProject } from "../plane";
import { MawesiModal } from "../ui/modal";
import { templatesService, useTemplates } from "./service";

export type TApplyTarget = { kind: "new"; moduleId?: string } | { kind: "existing"; issueId: string };

type Props = { target: TApplyTarget | null; onClose: () => void; workspaceSlug: string; projectId: string };

const selectClass = "w-full rounded-md border border-subtle bg-surface-1 px-2 py-1.5 text-13";

export const ApplyTemplateDialog = observer(function ApplyTemplateDialog({ target, onClose, workspaceSlug, projectId }: Props) {
  const t = useT();
  const navigate = useNavigate();
  const { getPartialProjectById } = useProject();
  const { subIssues, fetchIssue } = useIssueDetail();
  const { data: all } = useTemplates(workspaceSlug, projectId, !!target);
  const [templateId, setTemplateId] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // Para una tarea existente solo sirven las plantillas con subtareas.
  const templates = (all ?? []).filter((x) => target?.kind === "new" || x.subtasks.length > 0);

  useEffect(() => {
    if (!target) return;
    setName("");
    setError(null);
  }, [target]);
  useEffect(() => {
    if (!templates.some((x) => x.id === templateId)) setTemplateId(templates[0]?.id ?? "");
  }, [templates, templateId]);

  if (!target) return null;
  const selected = templates.find((x) => x.id === templateId);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!selected?.id) return;
    if (target.kind === "new" && !name.trim()) return setError(t("tpl.err_task_name"));
    setSaving(true);
    setError(null);
    try {
      if (target.kind === "new") {
        const r = await templatesService.apply(workspaceSlug, projectId, selected.id, { name: name.trim(), module_id: target.moduleId });
        setToast({ type: TOAST_TYPE.SUCCESS, title: t("tpl.created").replace("{n}", String(r.subtasks)) });
        onClose();
        navigate(`/${workspaceSlug}/browse/${getPartialProjectById(projectId)?.identifier}-${r.sequence_id}/`);
      } else {
        const r = await templatesService.apply(workspaceSlug, projectId, selected.id, { issue_id: target.issueId });
        await Promise.all([subIssues.fetchSubIssues(workspaceSlug, projectId, target.issueId), fetchIssue(workspaceSlug, projectId, target.issueId)]);
        setToast({ type: TOAST_TYPE.SUCCESS, title: t("tpl.added").replace("{n}", String(r.subtasks)) });
        onClose();
      }
    } catch (err: unknown) {
      setError((err as { error?: string })?.error ?? t("tree.error"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <MawesiModal isOpen onClose={onClose}>
      <form onSubmit={submit} className="space-y-4 px-5 py-4" data-mawesi="template-dialog">
        <h3 className="text-18 font-medium">{target.kind === "new" ? t("tpl.new_task") : t("tpl.add_subtasks")}</h3>
        {all && templates.length === 0 ? (
          <p className="text-13 text-secondary">
            {t("tpl.none_yet")}{" "}
            <Link to={`/${workspaceSlug}/settings/projects/${projectId}/mawesi-plantillas/`} className="text-accent-primary underline" onClick={onClose}>
              {t("tpl.go_settings")}
            </Link>
          </p>
        ) : (
          <>
            <label className="block space-y-1">
              <span className="text-13 text-secondary">{t("tpl.pick")}</span>
              <select name="template" value={templateId} onChange={(e) => setTemplateId(e.target.value)} className={selectClass}>
                {templates.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name}
                  </option>
                ))}
              </select>
            </label>
            {selected && selected.subtasks.length > 0 && (
              <p className="text-11 text-tertiary" data-mawesi="template-preview">
                {t("tpl.subtask_count").replace("{n}", String(selected.subtasks.length))}: {selected.subtasks.map((s) => s.name).join(" · ")}
              </p>
            )}
            {target.kind === "new" && (
              <label className="block space-y-1">
                <span className="text-13 text-secondary">{t("tpl.task_name")}</span>
                <Input name="task-name" value={name} onChange={(e) => setName(e.target.value)} className="w-full" autoFocus maxLength={255} />
              </label>
            )}
          </>
        )}
        {error && (
          <p className="text-13 text-danger-primary" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="lg" onClick={onClose}>
            {t("tree.cancel")}
          </Button>
          <Button type="submit" variant="primary" size="lg" loading={saving} disabled={!selected} data-mawesi="template-apply">
            {saving ? t("tpl.creating") : t("tpl.create")}
          </Button>
        </div>
      </form>
    </MawesiModal>
  );
});
