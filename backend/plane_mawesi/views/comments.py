# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Último comentario de varias tareas en una sola consulta (para el Hub: el resumen del informe de mejoras).

La API de Plane da los comentarios de a una tarea, y comentar no mueve `Issue.updated_at`: sin esto, saber cuál de las
subtareas tuvo el último comentario costaría una consulta por subtarea."""
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView as PlaneKeyAPIView
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import IssueComment

from plane_mawesi import services
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES

MAX_BATCH = 500


class LastCommentsMixin:
    """GET ?issue_ids=a,b → {issue_id: {id, comment_html, actor, created_at}} solo de las que tienen comentarios."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        ids = [i for i in request.GET.get("issue_ids", "").split(",") if i][:MAX_BATCH]
        if not ids:
            return Response({})
        try:
            rows = list(
                IssueComment.objects.filter(
                    workspace__slug=slug, project_id=project_id, issue_id__in=ids, issue__deleted_at__isnull=True
                )
                .order_by("issue_id", "-created_at")
                .distinct("issue_id")
                .values("id", "issue_id", "comment_html", "actor_id", "created_at")
            )
        except Exception:  # noqa: BLE001 - ids mal formados
            return Response({"error": "Ids inválidos."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            str(r["issue_id"]): {
                "id": str(r["id"]),
                "comment_html": r["comment_html"],
                "actor": str(r["actor_id"]) if r["actor_id"] else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        })


class LastCommentsEndpoint(LastCommentsMixin, PlaneSessionAPIView):
    pass


class LastCommentsKeyEndpoint(LastCommentsMixin, PlaneKeyAPIView):
    pass
