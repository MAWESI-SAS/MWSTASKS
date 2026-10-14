/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Configuración del proyecto → Campos (solo admins editan).
 */
import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { ListChecks, Pencil, Plus, Trash2 } from "lucide-react";
import { useT } from "../../i18n";
import type { TKey } from "../../i18n";
import {
  BreadcrumbLink, Breadcrumbs, Button, EUserPermissions, PageHead, SettingsContentWrapper, SettingsPageHeader, TOAST_TYPE,
  setToast, useUserPermissions,
} from "../../plane";
import { PropertyFormModal } from "../../properties/property-form-modal";
import { propertyService } from "../../properties/service";
import type { TProperty } from "../../properties/service";
import { useProjectProperties } from "../../properties/use-properties";
import { MawesiConfirm } from "../../ui/confirm";

function FieldsHeader() {
  const t = useT();
  return (
    <SettingsPageHeader
      leftItem={
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label={t("fields.settings_title")} icon={<ListChecks className="size-4 text-tertiary" />} />} />
        </Breadcrumbs>
      }
    />
  );
}

const PropertiesSettingsPage = observer(function PropertiesSettingsPage() {
  const t = useT();
  const { workspaceSlug = "", projectId = "" } = useParams();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const isAdmin = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId) === EUserPermissions.ADMIN;
  const { properties, mutate } = useProjectProperties(workspaceSlug, projectId);
  const [modal, setModal] = useState<{ open: boolean; prop?: TProperty }>({ open: false });
  const [toDelete, setToDelete] = useState<TProperty | null>(null);
  const [deleting, setDeleting] = useState(false);

  const confirmDelete = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await propertyService.remove(workspaceSlug, projectId, toDelete.id);
      await mutate();
      setToDelete(null);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("worklog.error") });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <SettingsContentWrapper header={<FieldsHeader />}>
      <PageHead title={t("fields.settings_title")} />
      <div className="w-full space-y-4" data-mawesi="properties-settings">
        <div className="flex items-start justify-between gap-4 border-b border-subtle pb-4">
          <div>
            <h3 className="font-heading text-18 font-semibold">{t("fields.settings_title")}</h3>
            <p className="text-13 text-secondary">{isAdmin ? t("fields.settings_help") : t("fields.only_admins")}</p>
          </div>
          {isAdmin && (
            <Button type="button" variant="primary" size="lg" onClick={() => setModal({ open: true })} data-mawesi="property-add">
              <Plus className="size-4" />
              {t("fields.add")}
            </Button>
          )}
        </div>
        {properties.length === 0 ? (
          <p className="text-13 text-tertiary">{t("fields.none")}</p>
        ) : (
          <ul className="divide-y divide-subtle rounded-lg border border-subtle">
            {properties.map((p) => (
              <li key={p.id} className="group flex items-center gap-3 px-4 py-3" data-mawesi="property-row">
                <div className="min-w-0 flex-1">
                  <p className="text-13 font-medium">{p.name}</p>
                  <p className="truncate text-11 text-secondary">
                    {t(`fields.type.${p.type}` as TKey)}
                    {p.options.length > 0 && ` · ${p.options.map((o) => o.name).join(", ")}`}
                  </p>
                </div>
                {isAdmin && (
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100">
                    <button type="button" aria-label={t("fields.edit")} data-mawesi="property-edit" onClick={() => setModal({ open: true, prop: p })} className="rounded p-1 hover:bg-layer-1">
                      <Pencil className="size-3.5" />
                    </button>
                    <button type="button" aria-label={t("worklog.delete")} data-mawesi="property-delete" onClick={() => setToDelete(p)} className="rounded p-1 hover:bg-layer-1">
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      <PropertyFormModal
        isOpen={modal.open}
        prop={modal.prop}
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
        title={t("fields.delete_title")}
        body={t("fields.delete_body")}
        confirmText={t("worklog.delete")}
        confirmingText={t("worklog.deleting")}
        cancelText={t("worklog.cancel")}
      />
    </SettingsContentWrapper>
  );
});

export default PropertiesSettingsPage;
