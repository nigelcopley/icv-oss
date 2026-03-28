"""
Audit subsystem concrete models.

These models are only created in the database when ICV_CORE_AUDIT_ENABLED=True.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from icv_core.exceptions import ImmutableRecordError
from icv_core.models.base import BaseModel


class AuditEntry(BaseModel):
    """
    Immutable record of a significant system event.

    AuditEntry records cannot be updated or deleted (raises ImmutableRecordError
    and ProtectedError respectively). For database-level enforcement, consuming
    projects can use PostgreSQL row-level security.
    """

    class EventType(models.TextChoices):
        SECURITY = "SECURITY", _("Security")
        DATA = "DATA", _("Data")
        SYSTEM = "SYSTEM", _("System")
        AUTHENTICATION = "AUTHENTICATION", _("Authentication")

    class Action(models.TextChoices):
        CREATE = "CREATE", _("Create")
        UPDATE = "UPDATE", _("Update")
        DELETE = "DELETE", _("Delete")
        LOGIN = "LOGIN", _("Login")
        LOGOUT = "LOGOUT", _("Logout")
        PASSWORD_CHANGED = "PASSWORD_CHANGED", _("Password changed")
        PERMISSION_DENIED = "PERMISSION_DENIED", _("Permission denied")
        CUSTOM = "CUSTOM", _("Custom")

    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
        db_index=True,
        verbose_name=_("event type"),
    )
    action = models.CharField(
        max_length=30,
        choices=Action.choices,
        db_index=True,
        verbose_name=_("action"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
        verbose_name=_("user"),
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("IP address"),
    )
    user_agent = models.TextField(
        blank=True,
        default="",
        verbose_name=_("user agent"),
    )
    target_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("target content type"),
    )
    target_object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("target object ID"),
    )
    target = GenericForeignKey("target_content_type", "target_object_id")
    description = models.TextField(
        blank=True,
        default="",
        verbose_name=_("description"),
    )
    metadata = models.JSONField(
        default=dict,
        verbose_name=_("metadata"),
        help_text=_("Arbitrary additional context for this audit entry."),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("audit entry")
        verbose_name_plural = _("audit entries")
        indexes = [
            models.Index(fields=["event_type", "action"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}/{self.action} at {self.created_at}"

    def save(self, *args, **kwargs) -> None:
        """AuditEntry is immutable — updates are not permitted."""
        if not self._state.adding:
            raise ImmutableRecordError("AuditEntry records are immutable and cannot be updated.")
        super().save(*args, **kwargs)
        from icv_core.audit.signals import audit_entry_created

        audit_entry_created.send(sender=self.__class__, instance=self)

    def delete(self, using=None, keep_parents=False):
        """AuditEntry records cannot be deleted."""
        raise models.ProtectedError(
            "AuditEntry records are immutable and cannot be deleted.",
            {self},
        )


class AdminActivityLog(BaseModel):
    """
    Record of an action taken by an admin user.

    Unlike AuditEntry this model allows updates but not deletion.
    """

    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_activity_logs",
        verbose_name=_("admin user"),
    )
    action_type = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name=_("action type"),
        help_text=_('e.g. "verify_coach", "approve_claim", "ban_user"'),
    )
    description = models.TextField(verbose_name=_("description"))
    target_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("target content type"),
    )
    target_object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("target object ID"),
    )
    target = GenericForeignKey("target_content_type", "target_object_id")
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("IP address"),
    )
    user_agent = models.TextField(
        blank=True,
        default="",
        verbose_name=_("user agent"),
    )
    metadata = models.JSONField(default=dict, verbose_name=_("metadata"))

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("admin activity log")
        verbose_name_plural = _("admin activity logs")

    def __str__(self) -> str:
        return f"{self.admin_user} — {self.action_type} at {self.created_at}"


class SystemAlert(BaseModel):
    """
    A raised system alert requiring admin attention.

    Alerts remain active until explicitly resolved. Connecting to the
    system_alert_raised signal allows consuming projects to trigger
    notifications via icv-notifications.
    """

    class AlertType(models.TextChoices):
        SECURITY = "security", _("Security")
        PAYMENT = "payment", _("Payment")
        CONTENT = "content", _("Content")
        SUPPORT = "support", _("Support")
        SYSTEM = "system", _("System")

    alert_type = models.CharField(
        max_length=20,
        choices=AlertType.choices,
        db_index=True,
        verbose_name=_("alert type"),
    )
    severity = models.CharField(
        max_length=20,
        db_index=True,
        verbose_name=_("severity"),
        help_text=_("One of: info, warning, error, critical (configurable via ICV_CORE_AUDIT_ALERT_SEVERITY_LEVELS)."),
    )
    title = models.CharField(max_length=255, verbose_name=_("title"))
    message = models.TextField(verbose_name=_("message"))
    related_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("related content type"),
    )
    related_object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("related object ID"),
    )
    related_object = GenericForeignKey("related_content_type", "related_object_id")
    metadata = models.JSONField(default=dict, verbose_name=_("metadata"))
    is_resolved = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("resolved"),
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_alerts",
        verbose_name=_("resolved by"),
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("resolved at"),
    )
    resolution_notes = models.TextField(
        blank=True,
        default="",
        verbose_name=_("resolution notes"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("system alert")
        verbose_name_plural = _("system alerts")

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.title}"

    def resolve(self, resolved_by, notes: str = "") -> None:
        """Mark this alert as resolved."""
        from icv_core.audit.signals import system_alert_resolved

        self.is_resolved = True
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save(update_fields=["is_resolved", "resolved_by", "resolved_at", "resolution_notes", "updated_at"])
        system_alert_resolved.send(sender=self.__class__, instance=self, resolved_by=resolved_by)
