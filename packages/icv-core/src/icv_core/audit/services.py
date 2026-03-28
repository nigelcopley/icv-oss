"""
Audit service functions.

Business logic for creating audit entries and managing system alerts.

Usage::

    from icv_core.audit.services import log_event, raise_alert, resolve_alert

    log_event(
        event_type="SECURITY",
        action="PERMISSION_DENIED",
        user=request.user,
        description="Attempted access to restricted resource",
        metadata={"resource": "/admin/"},
        request=request,
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.db.models import Model
    from django.http import HttpRequest

    from icv_core.audit.models import AuditEntry, SystemAlert

logger = logging.getLogger(__name__)


def log_event(
    event_type: str,
    action: str,
    user: AbstractUser | None = None,
    target: Model | None = None,
    description: str = "",
    metadata: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
    async_mode: bool = False,
) -> AuditEntry | None:
    """
    Create an AuditEntry record for a significant system event.

    Returns None immediately if ``ICV_CORE_AUDIT_ENABLED`` is False. No
    database write is performed and no Celery task is enqueued.

    Args:
        event_type: One of AuditEntry.EventType choices (SECURITY, DATA,
            SYSTEM, AUTHENTICATION).
        action: One of AuditEntry.Action choices (CREATE, UPDATE, DELETE,
            LOGIN, etc.).
        user: The user responsible for the event. May be None for system
            events.
        target: Optional model instance that the event relates to. Stored
            as a GenericForeignKey on the AuditEntry.
        description: Human-readable description of what happened.
        metadata: Arbitrary additional context (must be JSON-serialisable).
        request: Optional Django request. When provided, IP and user agent
            are extracted automatically (respects ICV_CORE_AUDIT_CAPTURE_*
            settings).
        async_mode: When True, the audit entry is written via Celery instead
            of inline. Requires Celery to be configured in the consuming
            project. Note: async_mode does not support the ``target``
            parameter as model instances are not serialisable.

    Returns:
        The created AuditEntry instance, or None if audit is disabled or
        async_mode is True (the entry is enqueued rather than returned).

    Raises:
        ImportError: If async_mode=True but Celery is not installed.
    """
    from icv_core.conf import get_setting

    if not get_setting("AUDIT_ENABLED", False):
        return None

    if async_mode:
        from icv_core.audit.tasks import log_event_async

        log_event_async.delay(
            event_type=event_type,
            action=action,
            user_id=str(user.pk) if user else None,
            description=description,
            metadata=metadata or {},
        )
        return None

    return _write_audit_entry(
        event_type=event_type,
        action=action,
        user=user,
        target=target,
        description=description,
        metadata=metadata or {},
        request=request,
    )


def _write_audit_entry(
    event_type: str,
    action: str,
    user: AbstractUser | None,
    description: str,
    metadata: dict[str, Any],
    target: Model | None = None,
    request: HttpRequest | None = None,
) -> AuditEntry:
    """
    Write an AuditEntry record synchronously.

    Internal function — call log_event() from external code.
    """
    from icv_core.audit.models import AuditEntry
    from icv_core.conf import get_setting

    capture_ip = get_setting("AUDIT_CAPTURE_IP", True)
    capture_ua = get_setting("AUDIT_CAPTURE_USER_AGENT", True)

    ip_address: str | None = None
    user_agent: str = ""

    if request is not None:
        if capture_ip:
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            ip_address = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else request.META.get("REMOTE_ADDR")

        if capture_ua:
            user_agent = request.META.get("HTTP_USER_AGENT", "")
    else:
        # Fall back to thread-local context set by AuditRequestMiddleware.
        from icv_core.audit.middleware import get_audit_context

        ctx = get_audit_context()
        if capture_ip:
            ip_address = ctx.get("ip_address")
        if capture_ua:
            user_agent = ctx.get("user_agent", "")
        if user is None:
            user = ctx.get("user")

    kwargs: dict[str, Any] = dict(
        event_type=event_type,
        action=action,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        description=description,
        metadata=metadata,
    )

    if target is not None:
        kwargs["target"] = target

    return AuditEntry.objects.create(**kwargs)


def raise_alert(
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> SystemAlert:
    """
    Create a SystemAlert record.

    Args:
        alert_type: One of SystemAlert.AlertType choices.
        severity: Severity level. Must be in ICV_CORE_AUDIT_ALERT_SEVERITY_LEVELS.
        title: Short title for the alert.
        message: Detailed alert message.
        metadata: Optional additional context.

    Returns:
        The created SystemAlert instance.

    Raises:
        ValueError: If ``severity`` is not in the configured severity levels.
    """
    from icv_core.audit.models import SystemAlert
    from icv_core.audit.signals import system_alert_raised
    from icv_core.conf import get_setting

    allowed_severities: list[str] = get_setting(
        "AUDIT_ALERT_SEVERITY_LEVELS",
        ["info", "warning", "error", "critical"],
    )
    if severity not in allowed_severities:
        raise ValueError(f"Invalid severity {severity!r}. Must be one of: {allowed_severities}.")

    alert = SystemAlert.objects.create(
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        metadata=metadata or {},
    )
    system_alert_raised.send(sender=SystemAlert, instance=alert)
    return alert


def resolve_alert(
    alert: SystemAlert,
    resolved_by: AbstractUser,
    notes: str = "",
) -> SystemAlert:
    """
    Resolve an active SystemAlert.

    Delegates to the model's ``resolve()`` method which fires the
    ``system_alert_resolved`` signal.

    Args:
        alert: The SystemAlert instance to resolve.
        resolved_by: The admin user resolving the alert.
        notes: Optional resolution notes.

    Returns:
        The resolved SystemAlert instance (mutated in place).

    Raises:
        ValueError: If the alert is already resolved.
    """
    if alert.is_resolved:
        raise ValueError(f"SystemAlert {alert.pk} is already resolved.")

    alert.resolve(resolved_by=resolved_by, notes=notes)
    return alert
