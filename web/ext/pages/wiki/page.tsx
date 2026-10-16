/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Wiki: un buscador sobre las Páginas de todos los proyectos (Plane CE solo las tiene por proyecto).
 * Busca en título y texto, sin importar tildes; agrupa por proyecto y abre la Página de Plane.
 */
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import useSWR from "swr";
import { FileText } from "lucide-react";
import { useT } from "../../i18n";
import { Input, PageHead } from "../../plane";
import { wikiService } from "../../wiki/service";
import type { TWikiPage } from "../../wiki/service";

const DEBOUNCE_MS = 300;
const plain = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Resalta la búsqueda en el texto (sin HTML: se arma con nodos de React). */
function Highlight({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const hay = plain(text);
  const needle = plain(query);
  const parts: ReactNode[] = [];
  let from = 0;
  for (let at = hay.indexOf(needle); at >= 0 && needle; at = hay.indexOf(needle, from)) {
    parts.push(text.slice(from, at), <mark key={at} className="rounded-sm bg-warning-subtle px-0.5 text-primary">{text.slice(at, at + needle.length)}</mark>);
    from = at + needle.length;
  }
  parts.push(text.slice(from));
  return <>{parts}</>;
}

export default function WikiPage() {
  const t = useT();
  const { workspaceSlug = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const [input, setInput] = useState(params.get("q") ?? "");
  const query = (params.get("q") ?? "").trim();

  useEffect(() => {
    const id = window.setTimeout(() => {
      const next = new URLSearchParams(params);
      if (input.trim()) next.set("q", input.trim());
      else next.delete("q");
      if (next.toString() !== params.toString()) setParams(next, { replace: true });
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [input, params, setParams]);

  const { data, isLoading } = useSWR(workspaceSlug ? ["mawesi-wiki", workspaceSlug, query] : null, () => wikiService.search(workspaceSlug, query), {
    revalidateOnFocus: false,
    keepPreviousData: true,
  });

  const groups = useMemo(() => {
    const m = new Map<string, { name: string; identifier: string; pages: TWikiPage[] }>();
    for (const p of data?.pages ?? []) {
      if (!m.has(p.project_id)) m.set(p.project_id, { name: p.project_name, identifier: p.project_identifier, pages: [] });
      m.get(p.project_id)!.pages.push(p);
    }
    return [...m.entries()];
  }, [data]);
  const total = data?.pages.length ?? 0;

  return (
    <>
      <PageHead title={t("wiki.title")} />
      <div className="flex h-full w-full flex-col gap-4 overflow-auto p-4 md:p-6" data-mawesi="wiki">
        <div className="space-y-2">
          <Input
            name="q"
            value={input}
            placeholder={t("wiki.search")}
            onChange={(e) => setInput(e.target.value)}
            className="w-full max-w-2xl"
            autoFocus
            data-mawesi="wiki-search"
          />
          <p className="text-13 text-secondary" data-mawesi="wiki-count">
            {isLoading && !data ? t("wiki.loading") : `${total} ${total === 1 ? t("wiki.count_one") : t("wiki.count")}`}
          </p>
          {data?.truncated && <p className="text-13 text-warning-primary">{t("wiki.truncated")}</p>}
        </div>
        {!isLoading && total === 0 && <p className="text-13 text-tertiary">{query ? t("wiki.empty_search") : t("wiki.empty")}</p>}
        {groups.map(([projectId, g]) => (
          <section key={projectId} className="space-y-1" data-mawesi="wiki-project">
            <h2 className="text-13 font-medium text-secondary">
              {g.name} <span className="text-tertiary">· {g.pages.length}</span>
            </h2>
            <ul className="divide-y divide-subtle rounded-lg border border-subtle">
              {g.pages.map((p) => (
                <li key={p.id}>
                  <Link
                    to={`/${workspaceSlug}/projects/${p.project_id}/pages/${p.id}/`}
                    className="flex gap-3 px-3 py-2 hover:bg-layer-1"
                    data-mawesi="wiki-result"
                  >
                    <FileText className="mt-0.5 size-4 flex-shrink-0 text-tertiary" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-13 font-medium text-primary">
                        <Highlight text={p.name || t("wiki.untitled")} query={query} />
                      </span>
                      {p.snippet && (
                        <span className="line-clamp-2 block text-11 text-secondary">
                          <Highlight text={p.snippet} query={query} />
                        </span>
                      )}
                    </span>
                    <span className="flex-shrink-0 text-11 text-tertiary">{p.updated_at?.slice(0, 10)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
