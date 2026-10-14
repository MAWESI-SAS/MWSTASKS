/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import useSWR from "swr";
import { EUserPermissions, useIssueDetail, useUser, useUserPermissions } from "../plane";
import { worklogService } from "./service";
import type { TWorklog } from "./service";

export const useWorklogs = (ws: string, projectId: string, issueId: string) => {
  const { data, isLoading, mutate } = useSWR(
    ws && projectId && issueId ? ["mawesi-worklogs", ws, projectId, issueId] : null,
    () => worklogService.list(ws, projectId, issueId),
    { revalidateOnFocus: false }
  );
  // OJO: usar el fetchActivities del store raíz (función flecha). El de `activity` es un método
  // de clase: desestructurado pierde `this` y falla en silencio.
  const { fetchActivities } = useIssueDetail();
  /** Recarga la lista y el historial de la tarea (donde aparece la fila de horas). */
  const refresh = async () => {
    await mutate();
    try {
      await fetchActivities(ws, projectId, issueId);
    } catch {
      // Las horas ya se guardaron; el historial se verá al recargar.
    }
  };
  const entries: TWorklog[] = data ?? [];
  const total = entries.reduce((s, e) => s + e.duration_minutes, 0);
  return { entries, total, isLoading, refresh };
};

/** Permisos en pantalla. El servidor vuelve a validar todo. */
export const useWorklogPermissions = (ws: string, projectId: string) => {
  const { data: me } = useUser();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const role = getProjectRoleByWorkspaceSlugAndProjectId(ws, projectId);
  const isAdmin = role === EUserPermissions.ADMIN;
  const canWrite = isAdmin || role === EUserPermissions.MEMBER;
  const canEdit = (e: TWorklog) => isAdmin || (canWrite && !!me && (e.member === me.id || e.created_by === me.id));
  return { canWrite, canEdit };
};
