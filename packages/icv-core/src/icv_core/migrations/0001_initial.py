"""Initial migration for icv_core — creates audit subsystem tables."""

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEntry",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        verbose_name="created at",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("SECURITY", "Security"),
                            ("DATA", "Data"),
                            ("SYSTEM", "System"),
                            ("AUTHENTICATION", "Authentication"),
                        ],
                        db_index=True,
                        max_length=20,
                        verbose_name="event type",
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("CREATE", "Create"),
                            ("UPDATE", "Update"),
                            ("DELETE", "Delete"),
                            ("LOGIN", "Login"),
                            ("LOGOUT", "Logout"),
                            ("PASSWORD_CHANGED", "Password changed"),
                            ("PERMISSION_DENIED", "Permission denied"),
                            ("CUSTOM", "Custom"),
                        ],
                        db_index=True,
                        max_length=30,
                        verbose_name="action",
                    ),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(blank=True, null=True, verbose_name="IP address"),
                ),
                (
                    "user_agent",
                    models.TextField(blank=True, default="", verbose_name="user agent"),
                ),
                (
                    "target_object_id",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="target object ID",
                    ),
                ),
                (
                    "description",
                    models.TextField(blank=True, default="", verbose_name="description"),
                ),
                (
                    "metadata",
                    models.JSONField(
                        default=dict,
                        help_text="Arbitrary additional context for this audit entry.",
                        verbose_name="metadata",
                    ),
                ),
                (
                    "target_content_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="contenttypes.contenttype",
                        verbose_name="target content type",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_entries",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="user",
                    ),
                ),
            ],
            options={
                "verbose_name": "audit entry",
                "verbose_name_plural": "audit entries",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AdminActivityLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        verbose_name="created at",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "action_type",
                    models.CharField(
                        db_index=True,
                        help_text='e.g. "verify_coach", "approve_claim", "ban_user"',
                        max_length=100,
                        verbose_name="action type",
                    ),
                ),
                (
                    "description",
                    models.TextField(verbose_name="description"),
                ),
                (
                    "target_object_id",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="target object ID",
                    ),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(blank=True, null=True, verbose_name="IP address"),
                ),
                (
                    "user_agent",
                    models.TextField(blank=True, default="", verbose_name="user agent"),
                ),
                (
                    "metadata",
                    models.JSONField(default=dict, verbose_name="metadata"),
                ),
                (
                    "admin_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admin_activity_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="admin user",
                    ),
                ),
                (
                    "target_content_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="contenttypes.contenttype",
                        verbose_name="target content type",
                    ),
                ),
            ],
            options={
                "verbose_name": "admin activity log",
                "verbose_name_plural": "admin activity logs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SystemAlert",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        verbose_name="created at",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "alert_type",
                    models.CharField(
                        choices=[
                            ("security", "Security"),
                            ("payment", "Payment"),
                            ("content", "Content"),
                            ("support", "Support"),
                            ("system", "System"),
                        ],
                        db_index=True,
                        max_length=20,
                        verbose_name="alert type",
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        db_index=True,
                        help_text="One of: info, warning, error, critical (configurable via ICV_CORE_AUDIT_ALERT_SEVERITY_LEVELS).",
                        max_length=20,
                        verbose_name="severity",
                    ),
                ),
                (
                    "title",
                    models.CharField(max_length=255, verbose_name="title"),
                ),
                (
                    "message",
                    models.TextField(verbose_name="message"),
                ),
                (
                    "related_object_id",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        verbose_name="related object ID",
                    ),
                ),
                (
                    "metadata",
                    models.JSONField(default=dict, verbose_name="metadata"),
                ),
                (
                    "is_resolved",
                    models.BooleanField(db_index=True, default=False, verbose_name="resolved"),
                ),
                (
                    "resolved_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="resolved at"),
                ),
                (
                    "resolution_notes",
                    models.TextField(blank=True, default="", verbose_name="resolution notes"),
                ),
                (
                    "related_content_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="contenttypes.contenttype",
                        verbose_name="related content type",
                    ),
                ),
                (
                    "resolved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="resolved_alerts",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="resolved by",
                    ),
                ),
            ],
            options={
                "verbose_name": "system alert",
                "verbose_name_plural": "system alerts",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="auditentry",
            index=models.Index(
                fields=["event_type", "action"],
                name="icv_core_au_event_t_9ac8b5_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="auditentry",
            index=models.Index(
                fields=["user", "created_at"],
                name="icv_core_au_user_id_c3e697_idx",
            ),
        ),
    ]
