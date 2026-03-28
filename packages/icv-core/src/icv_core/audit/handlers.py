"""
Audit signal handlers.

Connected by IcvCoreConfig.ready() only when ICV_CORE_AUDIT_ENABLED=True.
"""

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs) -> None:
    """Record a successful login as an authentication audit entry."""
    from icv_core.audit.services import _write_audit_entry

    _write_audit_entry(
        event_type="AUTHENTICATION",
        action="LOGIN",
        user=user,
        description=f"User {user} logged in.",
        metadata={},
        request=request,
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs) -> None:
    """Record a logout as an authentication audit entry."""
    from icv_core.audit.services import _write_audit_entry

    _write_audit_entry(
        event_type="AUTHENTICATION",
        action="LOGOUT",
        user=user,
        description=f"User {user} logged out.",
        metadata={},
        request=request,
    )


@receiver(user_login_failed)
def log_login_failure(sender, credentials, request, **kwargs) -> None:
    """Record a failed login attempt as a security audit entry."""
    from icv_core.audit.services import _write_audit_entry

    _write_audit_entry(
        event_type="SECURITY",
        action="LOGIN",
        user=None,
        description=f"Failed login attempt for: {credentials.get('username', 'unknown')}",
        metadata={"attempted_username": credentials.get("username", "")},
        request=request,
    )
