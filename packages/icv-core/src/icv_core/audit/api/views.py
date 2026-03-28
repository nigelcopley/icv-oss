"""DRF viewsets for the audit subsystem. All require staff access."""

from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from icv_core.audit.api.serializers import (
    AdminActivityLogSerializer,
    AuditEntrySerializer,
    SystemAlertSerializer,
)
from icv_core.audit.models import AdminActivityLog, AuditEntry, SystemAlert


class IsStaff(permissions.BasePermission):
    """Allow access only to staff users."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class AuditEntryViewSet(ReadOnlyModelViewSet):
    """Read-only viewset for AuditEntry. Staff only."""

    queryset = AuditEntry.objects.select_related("user", "target_content_type").all()
    serializer_class = AuditEntrySerializer
    permission_classes = [IsStaff]
    filterset_fields = ["event_type", "action", "user"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


class AdminActivityLogViewSet(ReadOnlyModelViewSet):
    """Read-only viewset for AdminActivityLog. Staff only."""

    queryset = AdminActivityLog.objects.select_related("admin_user", "target_content_type").all()
    serializer_class = AdminActivityLogSerializer
    permission_classes = [IsStaff]
    filterset_fields = ["admin_user", "action_type"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


class SystemAlertViewSet(ModelViewSet):
    """Viewset for SystemAlert management. Staff only."""

    queryset = SystemAlert.objects.select_related("resolved_by").all()
    serializer_class = SystemAlertSerializer
    permission_classes = [IsStaff]
    filterset_fields = ["alert_type", "severity", "is_resolved"]
    ordering_fields = ["created_at", "severity"]
    ordering = ["-created_at"]

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None) -> Response:
        """Resolve an active system alert."""
        alert = self.get_object()
        if alert.is_resolved:
            return Response(
                {"detail": "Alert is already resolved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        notes = request.data.get("resolution_notes", "")
        alert.resolve(resolved_by=request.user, notes=notes)
        serializer = self.get_serializer(alert)
        return Response(serializer.data)
