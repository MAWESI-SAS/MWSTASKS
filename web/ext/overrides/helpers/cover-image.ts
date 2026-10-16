/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Cover del perfil. `User.cover_image` es un URLField: exige URL absoluta. Plane la arma con
 * `getFileURL` = `API_BASE_URL + ruta`, pero con web y API en el mismo origen `API_BASE_URL` es ""
 * y queda relativa → `PATCH /api/users/me/` 400 "Enter a valid URL". Se completa con el origen
 * de la página. El cover de proyectos (TextField) no lo necesita pero no le hace daño.
 */
import { handleCoverImageChange as upstreamHandleCoverImageChange } from "@upstream/helpers/cover-image.helper";

export * from "@upstream/helpers/cover-image.helper";

export const handleCoverImageChange: typeof upstreamHandleCoverImageChange = async (...args) => {
  const payload = await upstreamHandleCoverImageChange(...args);
  if (payload?.cover_image?.startsWith("/")) payload.cover_image = new URL(payload.cover_image, window.location.origin).href;
  return payload;
};
