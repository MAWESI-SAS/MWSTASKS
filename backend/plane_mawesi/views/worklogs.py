# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Endpoints de horas. La lógica vive en mixins; cada API (sesión web o API key) los combina con su base de Plane."""
from django.db import transaction
from django.db.models import F, Sum
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView as PlaneKeyAPIView
from plane.app.permissions import ROLE
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import ProjectMember

from plane_mawesi import services
from plane_mawesi.models import Worklog
from plane_mawesi.serializers import WorklogSerializer

FORBIDDEN = Response({"error": "No tienes permiso para esto."}, status=status.HTTP_403_FORBIDDEN)
WRITE_ROLES = (ROLE.ADMIN.value, ROLE.MEMBER.value)


class PingEndpoint(PlaneSessionAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"mawesi": "ok"}, status=status.HTTP_200_OK)


class IssueWorklogsMixin:
    """GET lista / POST crea horas de un work item."""

    def get(self, request, slug, project_id, issue_id):
        if services.project_role(request.user, slug, project_id) not in WRITE_ROLES:
            return FORBIDDEN
        rows = Worklog.objects.filter(workspace__slug=slug, project_id=project_id, issue_id=issue_id)
        return Response(WorklogSerializer(rows, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, slug, project_id, issue_id):
        role = services.project_role(request.user, slug, project_id)
        if role not in WRITE_ROLES:
            return FORBIDDEN
        issue = services.get_issue(slug, project_id, issue_id)
        if issue is None:
            return Response({"error": "El work item no existe."}, status=status.HTTP_404_NOT_FOUND)
        serializer = WorklogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = serializer.validated_data.get("member") or request.user
        if member.id != request.user.id:
            if role != ROLE.ADMIN.value:
                return Response({"error": "Solo un admin puede registrar horas de otra persona."}, status=status.HTTP_403_FORBIDDEN)
            if not services.is_project_member(slug, project_id, member.id):
                return Response({"error": "La persona no es miembro del proyecto."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            worklog = serializer.save(
                issue=issue, project_id=project_id, workspace_id=issue.workspace_id, member=member
            )
            services.record_activity(worklog=worklog, actor_id=request.user.id, verb="created")
        return Response(WorklogSerializer(worklog).data, status=status.HTTP_201_CREATED)


class WorklogDetailMixin:
    """PATCH edita / DELETE borra un registro: su dueño (miembro) o un admin del proyecto."""

    def _get(self, request, slug, project_id, issue_id, pk):
        role = services.project_role(request.user, slug, project_id)
        worklog = Worklog.objects.filter(
            workspace__slug=slug, project_id=project_id, issue_id=issue_id, pk=pk
        ).first()
        return role, worklog

    def patch(self, request, slug, project_id, issue_id, pk):
        role, worklog = self._get(request, slug, project_id, issue_id, pk)
        if worklog is None:
            return Response({"error": "El registro no existe."}, status=status.HTTP_404_NOT_FOUND)
        if not services.can_edit(request.user, role, worklog):
            return FORBIDDEN
        old_minutes = worklog.duration_minutes
        serializer = WorklogSerializer(worklog, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_member = serializer.validated_data.get("member")
        if new_member and new_member.id != worklog.member_id:
            if role != ROLE.ADMIN.value:
                return Response({"error": "Solo un admin puede cambiar a quién se imputan las horas."}, status=status.HTTP_403_FORBIDDEN)
            if not services.is_project_member(slug, project_id, new_member.id):
                return Response({"error": "La persona no es miembro del proyecto."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            worklog = serializer.save()
            services.record_activity(worklog=worklog, actor_id=request.user.id, verb="updated", old_minutes=old_minutes)
        return Response(WorklogSerializer(worklog).data, status=status.HTTP_200_OK)

    def delete(self, request, slug, project_id, issue_id, pk):
        role, worklog = self._get(request, slug, project_id, issue_id, pk)
        if worklog is None:
            return Response({"error": "El registro no existe."}, status=status.HTTP_404_NOT_FOUND)
        if not services.can_edit(request.user, role, worklog):
            return FORBIDDEN
        with transaction.atomic():
            services.record_activity(
                worklog=worklog, actor_id=request.user.id, verb="deleted", old_minutes=worklog.duration_minutes
            )
            worklog.delete(soft=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorklogTotalsMixin:
    """GET ?issue_ids=a,b,c → {issue_id: minutos}. Para mostrar totales en listas sin tocar los payloads de Plane."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in WRITE_ROLES:
            return FORBIDDEN
        ids = [i for i in request.GET.get("issue_ids", "").split(",") if i][:500]
        return Response(services.totals_by_issue(slug, project_id, ids), status=status.HTTP_200_OK)


class WorklogReportMixin:
    """GET workspace: ?from=AAAA-MM-DD&to=AAAA-MM-DD[&project_id=][&member_id=] → filas + totales.

    Solo incluye proyectos donde quien consulta es admin o miembro.
    """

    def get(self, request, slug):
        try:
            date_from = services.parse_date(request.GET.get("from"))
            date_to = services.parse_date(request.GET.get("to"))
        except ValueError:
            return Response({"error": "Fechas en formato AAAA-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        projects = ProjectMember.objects.filter(
            member=request.user, workspace__slug=slug, is_active=True, role__in=WRITE_ROLES
        ).values_list("project_id", flat=True)
        rows = Worklog.objects.filter(workspace__slug=slug, project_id__in=projects)
        if date_from:
            rows = rows.filter(date__gte=date_from)
        if date_to:
            rows = rows.filter(date__lte=date_to)
        if request.GET.get("project_id"):
            rows = rows.filter(project_id=request.GET["project_id"])
        if request.GET.get("member_id"):
            rows = rows.filter(member_id=request.GET["member_id"])
        data = list(
            rows.select_related(None)
            .values("id", "date", "duration_minutes", "description", "member_id", "project_id", "issue_id")
            .annotate(
                member_name=F("member__display_name"),
                project_identifier=F("project__identifier"),
                issue_sequence=F("issue__sequence_id"),
                issue_name=F("issue__name"),
            )
            .order_by("date", "project_identifier", "issue_sequence")[:5000]
        )
        total = rows.aggregate(total=Sum("duration_minutes"))["total"] or 0
        return Response({"total_minutes": total, "count": len(data), "rows": data}, status=status.HTTP_200_OK)


# API web (cookie de sesión)
class IssueWorklogsEndpoint(IssueWorklogsMixin, PlaneSessionAPIView):
    pass


class WorklogDetailEndpoint(WorklogDetailMixin, PlaneSessionAPIView):
    pass


class WorklogTotalsEndpoint(WorklogTotalsMixin, PlaneSessionAPIView):
    pass


class WorklogReportEndpoint(WorklogReportMixin, PlaneSessionAPIView):
    pass


# API pública (X-Api-Key): AI Employees, script de migración
class IssueWorklogsKeyEndpoint(IssueWorklogsMixin, PlaneKeyAPIView):
    pass


class WorklogDetailKeyEndpoint(WorklogDetailMixin, PlaneKeyAPIView):
    pass


class WorklogTotalsKeyEndpoint(WorklogTotalsMixin, PlaneKeyAPIView):
    pass


class WorklogReportKeyEndpoint(WorklogReportMixin, PlaneKeyAPIView):
    pass
