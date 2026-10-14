/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * En lugar de "Danos una estrella en GitHub" (de Plane): enlace al código fuente de MWSTASKS.
 * Cumple AGPL-3.0 §13 (ofrecer el código a quien usa el sistema por la red).
 */
import { Code2 } from "lucide-react";
import { useT } from "../../i18n";
import { SOURCE_URL } from "../../brand/brand";

export function StarUsOnGitHubLink() {
  const t = useT();
  return (
    <a
      aria-label={t("brand.source_code")}
      title={t("brand.source_code_hint")}
      className="flex flex-shrink-0 items-center gap-1.5 rounded-sm bg-layer-2 px-3 py-1.5 text-primary"
      href={SOURCE_URL}
      target="_blank"
      rel="noopener noreferrer"
      data-mawesi="source-link"
    >
      <Code2 className="size-4" aria-hidden="true" />
      <span className="hidden text-11 font-medium sm:hidden md:block">{t("brand.source_code")}</span>
    </a>
  );
}
