/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Panel "Código" del detalle de la tarea: commits y pull requests (GitHub / Azure Repos) que la nombran. Solo
 * aparece si hay alguno. Los lee Celery cada pocos minutos (ver backend plane_mawesi/code.py).
 */
import { observer } from "mobx-react";
import useSWR from "swr";
import { GitCommitHorizontal, GitMerge, GitPullRequest, GitPullRequestClosed } from "lucide-react";
import { useT } from "../i18n";
import type { TKey } from "../i18n";
import { codeService } from "./service";
import type { TCodeLink } from "./service";

type Props = { workspaceSlug: string; projectId: string; issueId: string };

const ICON = { commit: GitCommitHorizontal, open: GitPullRequest, merged: GitMerge, closed: GitPullRequestClosed };
const STATE_CLASS: Record<string, string> = { open: "text-success-primary", merged: "text-accent-primary", closed: "text-danger-primary" };

const iconOf = (l: TCodeLink) => (l.kind === "commit" ? ICON.commit : (ICON[l.state as keyof typeof ICON] ?? GitPullRequest));

export const CodePanel = observer(function CodePanel({ workspaceSlug, projectId, issueId }: Props) {
  const t = useT();
  const { data } = useSWR(["mawesi-code-links", workspaceSlug, projectId, issueId], () => codeService.links(workspaceSlug, projectId, issueId), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
  if (!data?.length) return null;
  return (
    <div data-mawesi="code-panel" className="space-y-2">
      <h5 className="text-body-xs-medium">{t("code.title")}</h5>
      <ul className="space-y-1">
        {data.map((l) => {
          const Icon = iconOf(l);
          return (
            <li key={l.id} className="flex items-start gap-2 rounded-md px-1 py-1 hover:bg-layer-1" data-mawesi="code-link" data-kind={l.kind}>
              <Icon className={`mt-0.5 size-3.5 flex-shrink-0 ${l.kind === "pr" ? STATE_CLASS[l.state] ?? "" : "text-tertiary"}`} />
              <div className="min-w-0 flex-1">
                <a href={l.url} target="_blank" rel="noopener noreferrer" className="line-clamp-2 text-13 hover:underline">
                  {l.kind === "pr" ? `#${l.external_id} ` : ""}
                  {l.title}
                </a>
                <div className="truncate text-11 text-tertiary">
                  {l.repo} · {l.kind === "commit" ? l.external_id.slice(0, 7) : t(`code.state.${l.state}` as TKey) ?? l.state} · {l.author} ·{" "}
                  {new Date(l.happened_at).toLocaleDateString()}
                  {l.closed_issue && ` · ${t("code.closed_it")}`}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
});
