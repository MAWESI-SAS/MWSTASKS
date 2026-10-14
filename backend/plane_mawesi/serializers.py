# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime

from django.utils import timezone
from rest_framework import serializers

from plane_mawesi.models import MAX_MINUTES_PER_ENTRY, Property, PropertyOption, Worklog


class WorklogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Worklog
        fields = [
            "id", "issue", "project", "workspace", "member", "duration_minutes", "date", "description",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "issue", "project", "workspace", "created_by", "created_at", "updated_at"]
        extra_kwargs = {"member": {"required": False}}

    def validate_duration_minutes(self, value):
        if not 1 <= value <= MAX_MINUTES_PER_ENTRY:
            raise serializers.ValidationError(f"Debe estar entre 1 y {MAX_MINUTES_PER_ENTRY} minutos.")
        return value

    def validate_date(self, value):
        # Un día de margen por zonas horarias (el servidor está en UTC).
        if value > timezone.now().date() + datetime.timedelta(days=1):
            raise serializers.ValidationError("No se pueden registrar horas en fechas futuras.")
        return value


class PropertyOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyOption
        fields = ["id", "name", "color", "sort_order", "external_id"]


class PropertySerializer(serializers.ModelSerializer):
    options = PropertyOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = [
            "id", "project", "name", "type", "description", "sort_order", "is_active", "options",
            "external_source", "external_id", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "project", "options", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value

    def validate_type(self, value):
        if self.instance and value != self.instance.type:
            raise serializers.ValidationError("No se puede cambiar el tipo de un campo existente.")
        return value
