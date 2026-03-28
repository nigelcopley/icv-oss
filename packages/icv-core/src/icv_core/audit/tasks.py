"""
Celery tasks for the icv-core audit subsystem.

These tasks are only meaningful when ICV_CORE_AUDIT_ENABLED=True and Celery
is configured in the consuming project.
"""

from __future__ import annotations


def log_event_async(
    event_type: str,
    action: str,
    user_id: str | None,
    description: str,
    metadata: dict,
) -> None:
    """
    Write an AuditEntry asynchronously via Celery.

    Called by icv_core.audit.services.log_event when async_mode=True.
    This function is wrapped as a Celery task at import time if Celery is
    available; otherwise it falls back to a synchronous call with a warning.
    """
    from icv_core.audit.models import AuditEntry

    user = None
    if user_id is not None:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            pass

    AuditEntry.objects.create(
        event_type=event_type,
        action=action,
        user=user,
        description=description,
        metadata=metadata,
    )


def archive_old_entries() -> int:
    """
    Archive AuditEntry rows older than ICV_CORE_AUDIT_RETENTION_DAYS.

    Returns the number of entries processed.

    Note: This implementation logs a message and returns 0 until the archive
    storage backend is configured. Consuming projects should override the
    archive target via settings.
    """
    import logging
    from datetime import timedelta

    from django.utils import timezone

    from icv_core.audit.models import AuditEntry
    from icv_core.conf import ICV_CORE_AUDIT_RETENTION_DAYS

    logger = logging.getLogger(__name__)
    cutoff = timezone.now() - timedelta(days=ICV_CORE_AUDIT_RETENTION_DAYS)
    old_entries = AuditEntry.objects.filter(created_at__lt=cutoff)
    count = old_entries.count()

    # Placeholder: consuming projects implement their own archive backend.
    logger.info("icv_core.audit: %d entries eligible for archival (cutoff: %s).", count, cutoff)
    return count


# Wrap as Celery tasks if Celery is available
try:
    from celery import shared_task  # type: ignore[import]

    log_event_async = shared_task(log_event_async)  # type: ignore[assignment]
    archive_old_entries = shared_task(archive_old_entries)  # type: ignore[assignment]
except ImportError:
    pass
