# Audit models live under icv_core.audit but carry app_label="icv_core".
# They must be imported here so Django's app registry discovers them and
# migration detection works correctly.
from icv_core.audit.models import AdminActivityLog, AuditEntry, SystemAlert
from icv_core.models.base import BaseModel, TimestampedModel, UUIDModel
from icv_core.models.compliance import ComplianceModel
from icv_core.models.soft_delete import SoftDeleteModel

# Tenancy mixins — DEPRECATED. Use boundary.models.TenantModel instead.
# Kept for backwards compatibility; will be removed in a future release.
from icv_core.tenancy.mixins import TenantAwareMixin, TenantOwnedMixin

__all__ = [
    "UUIDModel",
    "TimestampedModel",
    "BaseModel",
    "SoftDeleteModel",
    "ComplianceModel",
    # tenancy
    "TenantAwareMixin",
    "TenantOwnedMixin",
    # audit
    "AuditEntry",
    "AdminActivityLog",
    "SystemAlert",
]
