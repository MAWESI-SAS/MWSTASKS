/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Configuración del workspace → Repositorios (solo admins del workspace): repos de GitHub o Azure Repos donde
 * MWSTASKS busca ids de tareas ("TQ-123") en commits y PRs. Muestra la última lectura y su error, y deja leer ahora.
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR from "swr";
import { FolderGit2, RefreshCw, Trash2 } from "lucide-react";
import { codeService } from "../../code/service";
import type { TCodeProvider, TCodeRepo } from "../../code/service";
import { useT } from "../../i18n";
import { apiError } from "../../lib/api-error";
import {
  BreadcrumbLink, Breadcrumbs, Button, EUserWorkspaceRoles, Input, PageHead, SettingsContentWrapper, SettingsPageHeader,
  TOAST_TYPE, setToast, useUserPermissions,
} from "../../plane";
import { MawesiConfirm } from "../../ui/confirm";
import { Toggle } from "../../ui/toggle";

const selectClass = "block h-9 rounded-md border border-subtle bg-surface-1 px-2 text-13 text-primary";
const PROVIDER_LABEL: Record<TCodeProvider, string> = { github: "GitHub", azure: "Azure Repos" };

function CodeHeader() {
  const t = useT();
  return (
    <SettingsPageHeader
      leftItem={
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label={t("code.settings_title")} icon={<FolderGit2 className="size-4 text-tertiary" />} />} />
        </Breadcrumbs>
      }
    />
  );
}

const CodeSettingsPage = observer(function CodeSettingsPage() {
  const t = useT();
  const { workspaceSlug = "" } = useParams();
  const { getWorkspaceRoleByWorkspaceSlug } = useUserPermissions();
  const isAdmin = getWorkspaceRoleByWorkspaceSlug(workspaceSlug) === EUserWorkspaceRoles.ADMIN;
  const { data, mutate } = useSWR(isAdmin ? ["mawesi-code-repos", workspaceSlug] : null, () => codeService.list(workspaceSlug));
  const [provider, setProvider] = useState<TCodeProvider>("github");
  const [path, setPath] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<TCodeRepo | null>(null);
  const [deleting, setDeleting] = useState(false);

  const replace = (repo: TCodeRepo) =>
    mutate((d) => d && { ...d, repos: d.repos.map((r) => (r.id === repo.id ? repo : r)) }, { revalidate: false });

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setAdding(true);
    try {
      const repo = await codeService.add(workspaceSlug, provider, path);
      setPath("");
      await mutate((d) => d && { ...d, repos: [...d.repos, repo] }, { revalidate: false });
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("code.added") });
    } catch (err) {
      setError(apiError(err, t("worklog.error")));
    } finally {
      setAdding(false);
    }
  };

  const sync = async (repo: TCodeRepo) => {
    setSyncing(repo.id);
    try {
      const fresh = await codeService.sync(workspaceSlug, repo.id);
      await replace(fresh);
      if (fresh.last_error) setToast({ type: TOAST_TYPE.ERROR, title: fresh.last_error });
      else setToast({ type: TOAST_TYPE.SUCCESS, title: `${t("code.synced")}: ${fresh.new_links ?? 0} ${t("code.new_links")}` });
    } catch (err) {
      setToast({ type: TOAST_TYPE.ERROR, title: apiError(err, t("worklog.error")) });
    } finally {
      setSyncing(null);
    }
  };

  const remove = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await codeService.remove(workspaceSlug, toDelete.id);
      await mutate((d) => d && { ...d, repos: d.repos.filter((r) => r.id !== toDelete.id) }, { revalidate: false });
      setToDelete(null);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("worklog.error") });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <SettingsContentWrapper header={<CodeHeader />}>
      <PageHead title={t("code.settings_title")} />
      <div className="w-full max-w-3xl space-y-6" data-mawesi="code-settings">
        <div className="border-b border-subtle pb-4">
          <h3 className="font-heading text-18 font-semibold">{t("code.settings_title")}</h3>
          <p className="text-13 text-secondary">{t("code.settings_help")}</p>
          <p className="mt-2 rounded-md bg-layer-1 px-3 py-2 text-13">
            {t("code.how")} <code className="rounded bg-layer-2 px-1">TQ-123</code> · <code className="rounded bg-layer-2 px-1">fixes TQ-123</code>
          </p>
        </div>

        {!isAdmin ? (
          <p className="text-13 text-tertiary">{t("code.only_admins")}</p>
        ) : (
          <>
            <form onSubmit={add} className="flex flex-wrap items-end gap-2">
              <label className="space-y-1">
                <span className="block text-13 text-secondary">{t("code.provider")}</span>
                <select name="provider" className={selectClass} value={provider} onChange={(e) => setProvider(e.target.value as TCodeProvider)}>
                  <option value="github">GitHub</option>
                  <option value="azure">Azure Repos</option>
                </select>
              </label>
              <label className="min-w-72 flex-1 space-y-1">
                <span className="block text-13 text-secondary">{t("code.repo")}</span>
                <Input
                  name="path"
                  value={path}
                  placeholder={provider === "github" ? "owner/repo" : "https://dev.azure.com/org/proyecto/_git/repo"}
                  onChange={(e) => setPath(e.target.value)}
                  className="h-9 w-full"
                />
              </label>
              <Button type="submit" variant="primary" size="lg" loading={adding} disabled={!path.trim()} data-mawesi="code-add">
                {t("code.add")}
              </Button>
            </form>
            {error && (
              <p className="text-13 text-danger-primary" role="alert">
                {error}
              </p>
            )}
            {data && !data.tokens[provider] && (
              <p className="text-13 text-warning-primary" data-mawesi="code-token-hint">
                {provider === "github" ? t("code.no_token_github") : t("code.no_token_azure")}
              </p>
            )}

            <div className="divide-y divide-subtle rounded-lg border border-subtle">
              {data?.repos.length === 0 && <p className="p-3 text-13 text-tertiary">{t("code.none")}</p>}
              {data?.repos.map((r) => (
                <div key={r.id} className="flex flex-wrap items-center gap-3 p-3" data-mawesi="code-repo" data-path={r.path}>
                  <div className="min-w-0 flex-1">
                    <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-13 font-medium hover:underline">
                      {r.path}
                    </a>
                    <div className="text-11 text-tertiary">
                      {PROVIDER_LABEL[r.provider]} · {r.links_found} {t("code.links")} ·{" "}
                      {r.last_synced_at ? `${t("code.last_sync")} ${new Date(r.last_synced_at).toLocaleString()}` : t("code.never")}
                    </div>
                    {r.last_error && (
                      <div className="text-11 text-danger-primary" data-mawesi="code-repo-error">
                        {r.last_error}
                      </div>
                    )}
                  </div>
                  <Toggle value={r.enabled} label={t("auto.enabled")} onChange={(v) => void codeService.setEnabled(workspaceSlug, r.id, v).then(replace)} />
                  <button
                    type="button"
                    onClick={() => void sync(r)}
                    disabled={syncing === r.id}
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-13 text-secondary hover:bg-layer-1 hover:text-primary disabled:opacity-50"
                    data-mawesi="code-sync"
                  >
                    <RefreshCw className={`size-3.5 ${syncing === r.id ? "animate-spin" : ""}`} />
                    {t("code.sync_now")}
                  </button>
                  <button type="button" onClick={() => setToDelete(r)} className="rounded p-1 hover:bg-layer-1" aria-label={t("code.remove")}>
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              ))}
            </div>
            <p className="text-11 text-tertiary">
              {t("code.every")} {data?.sync_minutes ?? 5} {t("code.minutes")}
            </p>
          </>
        )}
      </div>
      <MawesiConfirm
        isOpen={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={remove}
        isSubmitting={deleting}
        title={t("code.remove")}
        body={t("code.remove_body")}
        confirmText={t("code.remove")}
        confirmingText={t("worklog.deleting")}
        cancelText={t("worklog.cancel")}
      />
    </SettingsContentWrapper>
  );
});

export default CodeSettingsPage;
