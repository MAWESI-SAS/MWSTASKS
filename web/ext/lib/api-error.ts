/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Mensaje de error del servidor ({"error": "..."}). El APIService de Plane rechaza con el error de axios, así que el
 * cuerpo está en `response.data`.
 */
export const apiError = (err: unknown, fallback: string): string => {
  const e = err as { response?: { data?: { error?: string } }; error?: string };
  return e?.response?.data?.error ?? e?.error ?? fallback;
};
