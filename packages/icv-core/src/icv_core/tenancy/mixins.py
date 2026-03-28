"""Abstract model mixins for row-level tenant isolation.

Provides TenantAwareMixin and TenantOwnedMixin for models that need tenant
scoping. These mixins add a FK to the tenant model (configured via
ICV_TENANCY_TENANT_MODEL) and use TenantScopedManager for filtering.

Schema-level tenancy (via django-tenants) does not need these mixins — the
database schema provides isolation. These mixins are for row-level tenancy only.

NOTE: The tenant FK field name is fixed as "tenant". Consuming projects that need
a different field name should define the FK field explicitly in their models
rather than using these mixins.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from icv_core.tenancy.managers import TenantScopedManager


class TenantAwareMixin(models.Model):
    """
    Abstract mixin that adds a tenant FK and scoped manager.

    Row-level tenancy only. Schema-mode projects (django-tenants) don't need this.

    The FK field name is always "tenant". The tenant model is configurable via
    ICV_TENANCY_TENANT_MODEL (default: "auth.Group").

    The FK uses on_delete=PROTECT by default — the tenant cannot be deleted whilst
    records exist. Use TenantOwnedMixin if you want CASCADE behaviour (records are
    deleted when the tenant is deleted).

    The mixin provides a TenantScopedManager as the default manager, which includes
    .for_tenant() for filtering by tenant FK.

    Usage:
        from icv_core.tenancy import TenantAwareMixin
        from icv_core.models import BaseModel

        class Product(TenantAwareMixin, BaseModel):
            name = models.CharField(max_length=255)

        # Querying:
        from icv_core.tenancy import get_current_tenant
        tenant = get_current_tenant()
        products = Product.objects.for_tenant(tenant)

    Settings:
        ICV_TENANCY_TENANT_MODEL: str = "auth.Group" (default)
            Swappable tenant model. Consuming projects override this (e.g.,
            "icv_identity.Organisation"). The default is a no-op placeholder.
    """

    # Dynamic FK using string reference — Django resolves this lazily
    # We read from settings.ICV_TENANCY_TENANT_MODEL at import time
    tenant = models.ForeignKey(
        getattr(settings, "ICV_TENANCY_TENANT_MODEL", "auth.Group"),
        on_delete=models.PROTECT,
        db_index=True,
        related_name="%(app_label)s_%(class)s_set",
        verbose_name=_("tenant"),
    )

    objects = TenantScopedManager()

    class Meta:
        abstract = True


class TenantOwnedMixin(models.Model):
    """
    Abstract mixin with tenant FK using CASCADE.

    Record is deleted when the tenant is deleted. Use this for data that is
    "owned" by the tenant and has no meaning outside the tenant's context
    (e.g., invoices, orders, cart items).

    Use TenantAwareMixin (PROTECT) for data that should prevent tenant deletion
    (e.g., active subscriptions, unpaid invoices).

    Usage:
        from icv_core.tenancy import TenantOwnedMixin
        from icv_core.models import BaseModel

        class Invoice(TenantOwnedMixin, BaseModel):
            total = models.DecimalField(max_digits=10, decimal_places=2)

        # Invoice is deleted when the tenant is deleted.
    """

    # Dynamic FK with CASCADE using string reference
    tenant = models.ForeignKey(
        getattr(settings, "ICV_TENANCY_TENANT_MODEL", "auth.Group"),
        on_delete=models.CASCADE,
        db_index=True,
        related_name="%(app_label)s_%(class)s_set",
        verbose_name=_("tenant"),
    )

    objects = TenantScopedManager()

    class Meta:
        abstract = True
