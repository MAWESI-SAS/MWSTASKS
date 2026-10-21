/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Configuración del tablero del proyecto (un pedido por proyecto, compartido por todas las columnas y tarjetas).
 */
import useSWR from "swr";
import { boardService } from "./service";

export const boardKey = (ws: string, projectId: string) => ["mawesi-board", ws, projectId];

export const useBoardConfig = (ws: string | undefined, projectId: string | null | undefined) => {
  const { data } = useSWR(ws && projectId ? boardKey(ws, projectId) : null, () => boardService.config(ws!, projectId!), {
    revalidateOnFocus: false,
    shouldRetryOnError: false, // guests reciben 403: sin límites ni colores
    dedupingInterval: 60_000,
  });
  return data ?? null;
};
