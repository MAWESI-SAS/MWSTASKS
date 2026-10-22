/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Link con el ícono del sitio y su nombre (dev.azure.com, github.com…), como ClickUp. El ícono lo busca el servidor
 * (backend/plane_mawesi/favicons.py); si no hay, queda el ícono de link.
 */
import { useState } from "react";
import { useParams } from "react-router";
import { Link2 } from "lucide-react";
import { API_BASE_URL } from "../plane";

export function hostOf(url: string): string | null {
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u.hostname.toLowerCase() : null;
  } catch {
    return null;
  }
}

export function SiteIcon({ host, className = "size-3.5" }: { host: string | null; className?: string }) {
  const { workspaceSlug } = useParams();
  const [failed, setFailed] = useState<string | null>(null);
  if (!host || !workspaceSlug || failed === host) return <Link2 className={`${className} shrink-0 text-tertiary`} />;
  return (
    <img
      src={`${API_BASE_URL}/api/mawesi/workspaces/${workspaceSlug}/favicon/?host=${encodeURIComponent(host)}`}
      alt=""
      loading="lazy"
      className={`${className} shrink-0 rounded-[2px] object-contain`}
      onError={() => setFailed(host)}
    />
  );
}

export function LinkChip({ url, className = "" }: { url: string; className?: string }) {
  const host = hostOf(url);
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      title={url}
      data-mawesi="link-chip"
      className={`inline-flex min-w-0 items-center gap-1.5 text-body-xs-regular text-primary hover:underline ${className}`}
    >
      <SiteIcon host={host} />
      <span className="truncate">{host ? host.replace(/^www\./, "") : url}</span>
    </a>
  );
}
