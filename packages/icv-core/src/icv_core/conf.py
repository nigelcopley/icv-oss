"""
Package-level settings with defaults.

All settings are namespaced under ICV_CORE_* and accessed via this module.
Consuming projects override in their Django settings file.

Usage:
    from icv_core.conf import ICV_CORE_ALLOW_HARD_DELETE
    # or
    from icv_core.conf import get_setting
    allow = get_setting("ALLOW_HARD_DELETE", False)
"""

from django.conf import settings

# ---------------------------------------------------------------------------
# Core settings
# ---------------------------------------------------------------------------

# UUID version for primary keys (4 = random, 7 = time-sorted, requires Python 3.12+)
ICV_CORE_UUID_VERSION: int = getattr(settings, "ICV_CORE_UUID_VERSION", 4)

# Field name used for soft-delete filtering
ICV_CORE_SOFT_DELETE_FIELD: str = getattr(settings, "ICV_CORE_SOFT_DELETE_FIELD", "is_active")

# Whether BaseModel includes created_by/updated_by fields (requires CurrentUserMiddleware)
ICV_CORE_TRACK_CREATED_BY: bool = getattr(settings, "ICV_CORE_TRACK_CREATED_BY", False)

# Default ordering applied to BaseModel subclasses
ICV_CORE_DEFAULT_ORDERING: str = getattr(settings, "ICV_CORE_DEFAULT_ORDERING", "-created_at")

# Whether SoftDeleteModel.delete() performs a hard delete instead of raising ProtectedError
ICV_CORE_ALLOW_HARD_DELETE: bool = getattr(settings, "ICV_CORE_ALLOW_HARD_DELETE", False)

# ---------------------------------------------------------------------------
# Tenancy infrastructure settings
# ---------------------------------------------------------------------------

# Row-level tenancy only. Schema-level tenancy (django-tenants) is configured
# entirely in the consuming project.

# Swappable tenant model (dot-notation). Consuming projects override this
# (e.g., "icv_identity.Organisation"). Default is a no-op placeholder.
ICV_TENANCY_TENANT_MODEL: str = getattr(settings, "ICV_TENANCY_TENANT_MODEL", "auth.Group")

# When True (recommended for DEBUG=True), raises an assertion if a query on a
# TenantAware model runs without .for_tenant() scope (prevents accidental
# cross-tenant data leakage)
ICV_TENANCY_ENFORCE_SCOPING: bool = getattr(settings, "ICV_TENANCY_ENFORCE_SCOPING", False)

# ---------------------------------------------------------------------------
# Audit subsystem settings
# ---------------------------------------------------------------------------

# Master switch — no tables created, no signals connected when False
ICV_CORE_AUDIT_ENABLED: bool = getattr(settings, "ICV_CORE_AUDIT_ENABLED", False)

# Days to retain audit entries before archival
ICV_CORE_AUDIT_RETENTION_DAYS: int = getattr(settings, "ICV_CORE_AUDIT_RETENTION_DAYS", 365)

# Models excluded from AuditMixin auto-tracking (app_label.ModelName format)
ICV_CORE_AUDIT_EXCLUDE_MODELS: list[str] = getattr(settings, "ICV_CORE_AUDIT_EXCLUDE_MODELS", [])

# Whether AuditMixin captures old vs new field values on UPDATE
ICV_CORE_AUDIT_TRACK_FIELD_CHANGES: bool = getattr(settings, "ICV_CORE_AUDIT_TRACK_FIELD_CHANGES", True)

# Record IP address in audit entries
ICV_CORE_AUDIT_CAPTURE_IP: bool = getattr(settings, "ICV_CORE_AUDIT_CAPTURE_IP", True)

# Record user agent string in audit entries
ICV_CORE_AUDIT_CAPTURE_USER_AGENT: bool = getattr(settings, "ICV_CORE_AUDIT_CAPTURE_USER_AGENT", True)

# Automatically log CREATE/UPDATE/DELETE on all BaseModel subclasses
ICV_CORE_AUDIT_AUTO_MODEL_TRACKING: bool = getattr(settings, "ICV_CORE_AUDIT_AUTO_MODEL_TRACKING", False)

# Available severity levels for system alerts
ICV_CORE_AUDIT_ALERT_SEVERITY_LEVELS: list[str] = getattr(
    settings,
    "ICV_CORE_AUDIT_ALERT_SEVERITY_LEVELS",
    ["info", "warning", "error", "critical"],
)


def get_setting(name: str, default=None):
    """Retrieve an ICV_CORE_{name} setting with a fallback default."""
    return getattr(settings, f"ICV_CORE_{name}", default)
