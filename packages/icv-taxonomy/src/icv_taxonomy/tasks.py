"""Celery tasks for icv-taxonomy.

Celery is optional.  When not installed, a no-op ``shared_task`` decorator is
used so imports succeed and tasks can be called synchronously without a Celery
worker.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except ImportError:
    # Celery not installed — define a no-op decorator so imports don't fail and
    # the task body remains directly callable.
    def shared_task(func=None, **kwargs):  # type: ignore[misc]
        def decorator(f):
            return f

        if func is not None:
            return decorator(func)
        return decorator


@shared_task
def cleanup_orphaned_associations_task(model_label: str | None = None) -> dict:
    """Remove ``TermAssociation`` rows whose tagged object no longer exists.

    Generic-FK associations have no database-level cascade, so deleting a
    tagged object leaves its association rows behind as orphans (BR-TAX-018).
    Schedule this as a periodic Celery beat task to keep the table clean.

    Args:
        model_label: Optional ``"app_label.ModelName"`` to restrict the cleanup
            to a single content type. When ``None``, every content type with
            associations is checked.

    Returns:
        The cleanup statistics dict from
        :func:`icv_taxonomy.services.cleanup_orphaned_associations`
        (``{"checked": int, "orphaned": int, "removed": int}``).
    """
    from django.apps import apps

    from icv_taxonomy.services import cleanup_orphaned_associations

    model_class = None
    if model_label:
        app_label, model_name = model_label.split(".")
        model_class = apps.get_model(app_label, model_name)

    stats = cleanup_orphaned_associations(model_class=model_class)
    logger.info(
        "cleanup_orphaned_associations_task: checked=%d orphaned=%d removed=%d (model=%s)",
        stats["checked"],
        stats["orphaned"],
        stats["removed"],
        model_label or "all",
    )
    return stats
