"""DRF serializers for the audit subsystem."""

from rest_framework import serializers

from icv_core.audit.models import AdminActivityLog, AuditEntry, SystemAlert


class AuditEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEntry
        fields = [
            "id",
            "event_type",
            "action",
            "user",
            "ip_address",
            "user_agent",
            "target_content_type",
            "target_object_id",
            "description",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields


class AdminActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminActivityLog
        fields = [
            "id",
            "admin_user",
            "action_type",
            "description",
            "target_content_type",
            "target_object_id",
            "ip_address",
            "user_agent",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields


class SystemAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemAlert
        fields = [
            "id",
            "alert_type",
            "severity",
            "title",
            "message",
            "metadata",
            "is_resolved",
            "resolved_by",
            "resolved_at",
            "resolution_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_resolved",
            "resolved_by",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
