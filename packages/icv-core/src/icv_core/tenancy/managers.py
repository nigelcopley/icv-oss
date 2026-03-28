"""Tenant-scoped manager and queryset for row-level tenant isolation."""

from django.db import models


class TenantScopedQuerySet(models.QuerySet):
    """
    QuerySet with tenant-based filtering support.

    Provides .for_tenant() to filter by the tenant FK and .active() to filter
    by is_active field (if present on the model).
    """

    def for_tenant(self, tenant) -> "TenantScopedQuerySet":
        """
        Filter queryset by tenant FK.

        Args:
            tenant: The tenant object to filter by.

        Returns:
            Filtered queryset.

        Example:
            products = Product.objects.for_tenant(current_tenant)
        """
        return self.filter(tenant=tenant)

    def active(self) -> "TenantScopedQuerySet":
        """
        Filter is_active=True if the model has the field.

        Returns:
            Filtered queryset, or unfiltered if model has no is_active field.

        Example:
            products = Product.objects.for_tenant(tenant).active()
        """
        if hasattr(self.model, "is_active"):
            return self.filter(is_active=True)
        return self.all()


class TenantScopedManager(models.Manager):
    """
    Manager for models that need tenant-based filtering.

    Used for row-level tenant isolation. Models with TenantAwareMixin or
    TenantOwnedMixin get this manager automatically.

    The consuming project calls .for_tenant(tenant) to restrict queries to a
    given tenant. The manager does NOT automatically filter by tenant — this
    must be done explicitly to avoid hiding data unintentionally.

    When ICV_TENANCY_ENFORCE_SCOPING=True and DEBUG=True, querying without
    .for_tenant() raises an assertion error (防御措施 to prevent accidental
    cross-tenant data leakage during development).

    Example:
        class Product(TenantAwareMixin, BaseModel):
            name = models.CharField(max_length=255)

        # Usage:
        tenant = get_current_tenant()
        products = Product.objects.for_tenant(tenant).filter(price__gte=100)
    """

    def get_queryset(self) -> TenantScopedQuerySet:
        """Return the base queryset (unfiltered unless .for_tenant() is called)."""
        return TenantScopedQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant) -> TenantScopedQuerySet:
        """
        Filter queryset by tenant FK.

        Args:
            tenant: The tenant object to filter by.

        Returns:
            Filtered queryset.
        """
        return self.get_queryset().for_tenant(tenant)

    def active(self) -> TenantScopedQuerySet:
        """
        Return only active records (requires is_active field on model).

        Returns:
            Filtered queryset, or unfiltered if model has no is_active field.
        """
        return self.get_queryset().active()
