"""Tenancy infrastructure for row-level multi-tenant isolation.

.. deprecated::
    This module is superseded by django-boundary (APP-019). Use
    ``boundary.models.TenantModel`` instead of ``TenantAwareMixin``,
    ``boundary.context.TenantContext`` instead of ``get_current_tenant()``,
    etc. This module remains for backwards compatibility and will be
    removed in a future release.

Provides abstract mixins, managers, and context services for row-level tenant
isolation. Schema-level tenancy (via django-tenants) is configured entirely in
the consuming project and does not require these tools.

Migration guide:
    icv_core.tenancy.TenantAwareMixin   → boundary.models.TenantModel
    icv_core.tenancy.TenantOwnedMixin   → boundary.models.TenantModel (CASCADE is default)
    icv_core.tenancy.TenantScopedManager → boundary.models.TenantManager (auto-filtering)
    icv_core.tenancy.get_current_tenant  → boundary.context.TenantContext.get()
    icv_core.tenancy.set_current_tenant  → boundary.context.TenantContext.set()
    icv_core.tenancy.clear_current_tenant → boundary.context.TenantContext.clear()
    icv_core.tenancy.tenant_context      → boundary.context.TenantContext.using()
"""

import warnings

from icv_core.tenancy.context import (
    clear_current_tenant,
    get_current_tenant,
    set_current_tenant,
    tenant_context,
)
from icv_core.tenancy.managers import TenantScopedManager, TenantScopedQuerySet
from icv_core.tenancy.mixins import TenantAwareMixin, TenantOwnedMixin

warnings.warn(
    "icv_core.tenancy is deprecated. Use django-boundary instead. See APP-019 spec for migration guide.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    # Context management
    "get_current_tenant",
    "set_current_tenant",
    "clear_current_tenant",
    "tenant_context",
    # Managers
    "TenantScopedManager",
    "TenantScopedQuerySet",
    # Mixins
    "TenantAwareMixin",
    "TenantOwnedMixin",
]
