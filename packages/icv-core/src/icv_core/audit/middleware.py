"""AuditRequestMiddleware — captures request context for audit entries."""

import threading

from django.utils.deprecation import MiddlewareMixin

_audit_context = threading.local()


def get_audit_context() -> dict:
    """
    Return the current request's audit context.

    Returns an empty dict outside of a request context.
    """
    return getattr(_audit_context, "context", {})


class AuditRequestMiddleware(MiddlewareMixin):
    """
    Captures the current request's user, IP address, and user agent so that
    audit entries can be enriched with request context.

    Required when ICV_CORE_AUDIT_ENABLED=True. Must be placed after
    Django's AuthenticationMiddleware in the MIDDLEWARE setting.

    Example::

        MIDDLEWARE = [
            ...
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "icv_core.audit.middleware.AuditRequestMiddleware",
            ...
        ]
    """

    def process_request(self, request) -> None:
        from icv_core.conf import ICV_CORE_AUDIT_CAPTURE_IP, ICV_CORE_AUDIT_CAPTURE_USER_AGENT

        context: dict = {
            "user": getattr(request, "user", None),
        }

        if ICV_CORE_AUDIT_CAPTURE_IP:
            context["ip_address"] = self._get_client_ip(request)

        if ICV_CORE_AUDIT_CAPTURE_USER_AGENT:
            context["user_agent"] = request.META.get("HTTP_USER_AGENT", "")

        _audit_context.context = context

    def process_response(self, request, response):
        _audit_context.context = {}
        return response

    def process_exception(self, request, exception) -> None:
        _audit_context.context = {}

    @staticmethod
    def _get_client_ip(request) -> str | None:
        """Extract the real client IP, respecting X-Forwarded-For."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
