# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Endpoints de campos propios (definición por proyecto y valores por work item)."""
from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView as PlaneKeyAPIView
from plane.app.permissions import ROLE
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView

from plane_mawesi import properties as P
from plane_mawesi import services
from plane_mawesi.models import Property, PropertyValue
from plane_mawesi.serializers import PropertySerializer

FORBIDDEN = Response({"error": "No tienes permiso para esto."}, status=status.HTTP_403_FORBIDDEN)
READ_ROLES = (ROLE.ADMIN.value, ROLE.MEMBER.value)
DUPLICATE = Response({"error": "Ya existe un campo con ese nombre en el proyecto."}, status=status.HTTP_400_BAD_REQUEST)


def _props(slug, project_id):
    return Property.objects.filter(workspace__slug=slug, project_id=project_id, is_active=True).prefetch_related("options")


class PropertiesMixin:
    """GET lista (admin y miembro) / POST crea (admin) los campos del proyecto."""

    def get(self, request, slug, project_id):
        role = services.project_role(request.user, slug, project_id)
        if role not in READ_ROLES:
            return FORBIDDEN
        data = PropertySerializer(_props(slug, project_id), many=True).data
        if request.GET.get("include_removed") == "1" and role == ROLE.ADMIN.value:
            # Para la copia desde ClickUp: los campos que alguien borró o desactivó acá no se vuelven a crear.
            gone = Property.all_objects.filter(workspace__slug=slug, project_id=project_id).exclude(external_id="").filter(
                Q(deleted_at__isnull=False) | Q(is_active=False))
            data = list(data) + [{"id": str(p.id), "name": p.name, "external_source": p.external_source,
                                  "external_id": p.external_id, "removed": True} for p in gone]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        serializer = PropertySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from plane.db.models import Project

        project = Project.objects.filter(workspace__slug=slug, pk=project_id).first()
        if project is None:
            return Response({"error": "El proyecto no existe."}, status=status.HTTP_404_NOT_FOUND)
        try:
            with transaction.atomic():
                prop = serializer.save(project=project, workspace_id=project.workspace_id)
                P.upsert_options(prop, request.data.get("options") or [])
        except IntegrityError:
            return DUPLICATE
        prop = _props(slug, project_id).get(pk=prop.pk)
        return Response(PropertySerializer(prop).data, status=status.HTTP_201_CREATED)


class PropertyDetailMixin:
    """PATCH edita (nombre, descripción, orden, opciones) / DELETE borra un campo. Solo admin."""

    def patch(self, request, slug, project_id, property_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        prop = _props(slug, project_id).filter(pk=property_id).first()
        if prop is None:
            return Response({"error": "El campo no existe."}, status=status.HTTP_404_NOT_FOUND)
        serializer = PropertySerializer(prop, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save()
                if "options" in request.data:
                    P.upsert_options(prop, request.data.get("options") or [])
        except IntegrityError:
            return DUPLICATE
        return Response(PropertySerializer(_props(slug, project_id).get(pk=prop.pk)).data, status=status.HTTP_200_OK)

    def delete(self, request, slug, project_id, property_id):
        if services.project_role(request.user, slug, project_id) != ROLE.ADMIN.value:
            return FORBIDDEN
        prop = _props(slug, project_id).filter(pk=property_id).first()
        if prop is None:
            return Response({"error": "El campo no existe."}, status=status.HTTP_404_NOT_FOUND)
        prop.delete()  # soft delete de Plane: los valores quedan en la base, ocultos
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssueValuesMixin:
    """GET {property_id: valor} / PATCH {"values": {property_id: valor|null}} de un work item."""

    def get(self, request, slug, project_id, issue_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        issue = services.get_issue(slug, project_id, issue_id)
        if issue is None:
            return Response({"error": "El work item no existe."}, status=status.HTTP_404_NOT_FOUND)
        return Response(P.values_for_issue(issue), status=status.HTTP_200_OK)

    def patch(self, request, slug, project_id, issue_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        issue = services.get_issue(slug, project_id, issue_id)
        if issue is None:
            return Response({"error": "El work item no existe."}, status=status.HTTP_404_NOT_FOUND)
        changes = request.data.get("values")
        if not isinstance(changes, dict) or not changes:
            return Response({"error": 'Enviar {"values": {property_id: valor}}.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            data = P.set_values(issue=issue, changes=changes, actor_id=request.user.id)
        except P.InvalidValue as e:
            return Response({"errors": e.args[0]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data, status=status.HTTP_200_OK)


class ValuesBatchMixin:
    """GET ?issue_ids=a,b → {issue_id: {property_id: valor}} (para listas y reportes)."""

    def get(self, request, slug, project_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        ids = [i for i in request.GET.get("issue_ids", "").split(",") if i][:500]
        props = {str(p.id): (p, P.option_names(p)) for p in _props(slug, project_id)}
        out: dict = {}
        rows = PropertyValue.objects.filter(
            workspace__slug=slug, project_id=project_id, issue_id__in=ids, property_id__in=list(props.keys())
        ).values("issue_id", "property_id", "value")
        for r in rows:
            prop, names = props[str(r["property_id"])]
            v = P.readable(prop, r["value"], names)
            if v is not None:
                out.setdefault(str(r["issue_id"]), {})[str(r["property_id"])] = v
        return Response(out, status=status.HTTP_200_OK)


class PropertiesEndpoint(PropertiesMixin, PlaneSessionAPIView):
    pass


class PropertyDetailEndpoint(PropertyDetailMixin, PlaneSessionAPIView):
    pass


class IssueValuesEndpoint(IssueValuesMixin, PlaneSessionAPIView):
    pass


class ValuesBatchEndpoint(ValuesBatchMixin, PlaneSessionAPIView):
    pass


class PropertiesKeyEndpoint(PropertiesMixin, PlaneKeyAPIView):
    pass


class PropertyDetailKeyEndpoint(PropertyDetailMixin, PlaneKeyAPIView):
    pass


class IssueValuesKeyEndpoint(IssueValuesMixin, PlaneKeyAPIView):
    pass


class ValuesBatchKeyEndpoint(ValuesBatchMixin, PlaneKeyAPIView):
    pass
