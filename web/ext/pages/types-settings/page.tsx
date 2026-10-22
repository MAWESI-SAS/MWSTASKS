/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Configuración del proyecto → Tipos: tipos de tarea con sus propios campos (como Jira). Solo admins editan.
 */
import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR from "swr";
import { Pencil, Plus, Shapes, Star, Trash2 } from "lucide-react";
import { groupModules } from "../../folders/group";
import { useT } from "../../i18n";
import {
  BreadcrumbLink, Breadcrumbs, Button, EUserPermissions, PageHead, SettingsContentWrapper, SettingsPageHeader, TOAST_TYPE,
  setToast, useModule, useUserPermissions,
} from "../../plane";
import { useProjectProperties } from "../../properties/use-properties";
import { typeService } from "../../types/service";
import type { TWorkItemType } from "../../types/service";
import { TypeBadge } from "../../types/type-badge";
import { TypeFormModal } from "../../types/type-form-modal";
import { useProjectTypes } from "../../types/use-types";
import { MawesiConfirm } from "../../ui/confirm";

function TypesHeader() {
  const t = useT();
  return (
    <SettingsPageHeader
      leftItem={
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label={t("types.title")} icon={<Shapes className="size-4 text-tertiary" />} />} />
        </Breadcrumbs>
      }
    />
  );
}

const TypesSettingsPage = observer(function TypesSettingsPage() {
  const t = useT();
  const { workspaceSlug = "", projectId = "" } = useParams();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const isAdmin = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId) === EUserPermissions.ADMIN;
  const { types, mutate } = useProjectTypes(workspaceSlug, projectId);
  const { properties } = useProjectProperties(workspaceSlug, projectId);
  const moduleStore = useModule();
  useSWR(workspaceSlug && projectId ? ["mawesi-types-modules", workspaceSlug, projectId] : null, () => moduleStore.fetchModules(workspaceSlug, projectId), {
    revalidateOnFocus: false,
  });
  const tree = groupModules(moduleStore.getProjectModuleDetails(projectId) ?? []);
  const folders = [...tree.folders, ...(tree.loose.length ? [{ name: "", lists: tree.loose }] : [])];
  const listName = new Map(folders.flatMap((f) => f.lists.map((l) => [l.id, f.name ? `${f.name} / ${l.name}` : l.name] as const)));
  const fieldName = new Map(properties.map((p) => [p.id, p.name]));

  const [modal, setModal] = useState<{ open: boolean; type?: TWorkItemType }>({ open: false });
  const [toDelete, setToDelete] = useState<TWorkItemType | null>(null);
  const [deleting, setDeleting] = useState(false);

  const confirmDelete = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await typeService.remove(workspaceSlug, projectId, toDelete.id);
      await mutate();
      setToDelete(null);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("worklog.error") });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <SettingsContentWrapper header={<TypesHeader />}>
      <PageHead title={t("types.title")} />
      <div className="w-full space-y-4" data-mawesi="types-settings">
        <div className="flex items-start justify-between gap-4 border-b border-subtle pb-4">
          <div>
            <h3 className="font-heading text-18 font-semibold">{t("types.title")}</h3>
            <p className="text-13 text-secondary">{isAdmin ? t("types.help") : t("fields.only_admins")}</p>
          </div>
          {isAdmin && (
            <Button type="button" variant="primary" size="lg" onClick={() => setModal({ open: true })} data-mawesi="type-add">
              <Plus className="size-4" />
              {t("types.add")}
            </Button>
          )}
        </div>
        {types.length === 0 ? (
          <p className="text-13 text-tertiary">{t("types.none")}</p>
        ) : (
          <ul className="divide-y divide-subtle rounded-lg border border-subtle">
            {types.map((ty) => (
              <li key={ty.id} className="group flex items-start gap-3 px-4 py-3" data-mawesi="type-row">
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="flex items-center gap-2 text-13 font-medium">
                    <TypeBadge type={ty} />
                    {ty.is_default && (
                      <span className="inline-flex items-center gap-1 rounded-sm bg-layer-1 px-1.5 text-11 text-secondary">
                        <Star className="size-3" />
                        {t("types.default_badge")}
                      </span>
                    )}
                  </p>
                  {ty.description && <p className="text-11 text-secondary">{ty.description}</p>}
                  <p className="text-11 text-secondary">
                    <span className="text-tertiary">{t("types.fields")}: </span>
                    {ty.property_ids.length ? ty.property_ids.map((id) => fieldName.get(id)).filter(Boolean).join(", ") : t("types.no_fields")}
                  </p>
                  <p className="text-11 text-secondary">
                    <span className="text-tertiary">{t("types.lists")}: </span>
                    {ty.module_ids.length ? ty.module_ids.map((id) => listName.get(id)).filter(Boolean).join(", ") : "—"}
                  </p>
                </div>
                {isAdmin && (
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100">
                    <button type="button" aria-label={t("types.edit")} data-mawesi="type-edit" onClick={() => setModal({ open: true, type: ty })} className="rounded p-1 hover:bg-layer-1">
                      <Pencil className="size-3.5" />
                    </button>
                    <button type="button" aria-label={t("worklog.delete")} data-mawesi="type-delete" onClick={() => setToDelete(ty)} className="rounded p-1 hover:bg-layer-1">
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      <TypeFormModal
        isOpen={modal.open}
        type={modal.type}
        types={types}
        properties={properties}
        folders={folders}
        onClose={() => setModal((m) => ({ ...m, open: false }))}
        onSaved={() => mutate()}
        workspaceSlug={workspaceSlug}
        projectId={projectId}
      />
      <MawesiConfirm
        isOpen={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={confirmDelete}
        isSubmitting={deleting}
        title={t("types.delete_title")}
        body={t("types.delete_body")}
        confirmText={t("worklog.delete")}
        confirmingText={t("worklog.deleting")}
        cancelText={t("worklog.cancel")}
      />
    </SettingsContentWrapper>
  );
});

export default TypesSettingsPage;
