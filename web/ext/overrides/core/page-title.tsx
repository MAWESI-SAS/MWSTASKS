/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Título de la pestaña: cambia "Plane" por la marca y usa el título MAWESI por defecto.
 */
import { useEffect } from "react";
import { APP_TITLE, PRODUCT_NAME } from "../../brand/brand";

type PageHeadTitleProps = { title?: string; description?: string };

export function PageHead({ title }: PageHeadTitleProps) {
  useEffect(() => {
    if (title) document.title = title.replace(/(?<![\w.])Plane(?!\w)/g, PRODUCT_NAME);
    else document.title = APP_TITLE;
  }, [title]);
  return null;
}
