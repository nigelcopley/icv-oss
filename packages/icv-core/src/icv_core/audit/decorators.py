"""
@audited decorator — record an AuditEntry on each decorated call.

Usage::

    from icv_core.audit.decorators import audited

    @audited(event_type="DATA", action="EXPORT")
    def export_report(user, report_id):
        ...

    # On a class-based view:
    from django.utils.decorators import method_decorator

    @method_decorator(audited(event_type="DATA", action="VIEW"), name="dispatch")
    class SensitiveReportView(LoginRequiredMixin, View):
        ...
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any


def audited(
    event_type: str,
    action: str,
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> Callable:
    """
    Decorator that records an AuditEntry when the decorated function is called.

    The decorator extracts the ``request`` argument automatically if it is
    present as the first positional argument (views) or as a keyword argument.
    The ``user`` is extracted from ``request.user`` when available.

    Args:
        event_type: One of AuditEntry.EventType choices.
        action: One of AuditEntry.Action choices.
        description: Optional human-readable description.
        metadata: Optional additional context.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from icv_core.audit.services import log_event

            # Attempt to extract request from args (views) or kwargs
            request = None
            user = None

            if args:
                first_arg = args[0] if not hasattr(args[0], "dispatch") else (args[1] if len(args) > 1 else None)
                from django.http import HttpRequest

                if isinstance(first_arg, HttpRequest):
                    request = first_arg
                    user = getattr(request, "user", None)

            if request is None:
                request = kwargs.get("request")
                if request:
                    user = getattr(request, "user", None)

            log_event(
                event_type=event_type,
                action=action,
                user=user,
                description=description,
                metadata=metadata or {},
                request=request,
            )
            return func(*args, **kwargs)

        return wrapper

    return decorator
