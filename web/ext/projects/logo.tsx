/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * `Logo` de "@plane/propel/emoji-icon-picker" (lo reemplaza el módulo virtual de vite.ext.config.ts): si el logo
 * trae `image.url` (logo con imagen propia, ver backend plane_mawesi/views/project_logo.py) dibuja la imagen; si
 * no, el emoji o ícono de Plane.
 */
import type { ComponentProps } from "react";
import { PlaneLogo } from "../plane";

export type TLogoImage = { asset_id?: string; url?: string };

export const logoImageUrl = (logo: unknown): string | undefined =>
  (logo as { image?: TLogoImage } | undefined)?.image?.url || undefined;

export function Logo(props: ComponentProps<typeof PlaneLogo>) {
  const url = logoImageUrl(props.logo);
  if (!url) return <PlaneLogo {...props} />;
  const size = props.size ?? 16;
  // El nombre del proyecto siempre va al lado: la imagen es decorativa (alt vacío).
  return (
    <img
      src={url}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      className="shrink-0 rounded-sm object-contain"
      style={{ width: size, height: size }}
      data-mawesi="project-logo"
    />
  );
}
