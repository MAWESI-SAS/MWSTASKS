/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Botón del detalle de la tarea: agrega las subtareas de una plantilla (p. ej. las fases de un requerimiento).
 * Solo aparece si el proyecto tiene alguna plantilla con subtareas y la tarea se puede editar.
 */
import { useState } from "react";
import { LayoutTemplate } from "lucide-react";
import { useT } from "../i18n";
import { Button } from "../plane";
import { ApplyTemplateDialog } from "./apply-dialog";
import { useTemplates } from "./service";

type Props = { workspaceSlug: string; projectId: string; issueId: string; disabled?: boolean };

export function TemplateSubtasksButton({ workspaceSlug, projectId, issueId, disabled }: Props) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const { data } = useTemplates(workspaceSlug, projectId, !disabled);
  if (disabled || !data?.some((x) => x.subtasks.length > 0)) return null;
  return (
    <>
      <Button type="button" variant="secondary" size="sm" prependIcon={<LayoutTemplate />} onClick={() => setOpen(true)} data-mawesi="template-subtasks">
        {t("tpl.add_subtasks")}
      </Button>
      <ApplyTemplateDialog
        target={open ? { kind: "existing", issueId } : null}
        onClose={() => setOpen(false)}
        workspaceSlug={workspaceSlug}
        projectId={projectId}
      />
    </>
  );
}
