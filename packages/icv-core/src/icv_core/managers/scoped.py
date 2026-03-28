"""Scoped manager for row-level tenant isolation."""

from django.db import models


class ScopedQuerySet(models.QuerySet):
    """QuerySet with scope-based filtering support."""

    def for_scope(self, scope_field: str, scope_value) -> "ScopedQuerySet":
        """Filter by an arbitrary scope field and value."""
        return self.filter(**{scope_field: scope_value})

    def active(self) -> "ScopedQuerySet":
        """Filter is_active=True if the model has the field."""
        if hasattr(self.model, "is_active"):
            return self.filter(is_active=True)
        return self.all()


class ScopedManager(models.Manager):
    """
    Manager for models that need scope-based filtering.

    Used for row-level tenant isolation. The consuming project calls
    `for_scope("organisation", org)` to restrict queries to a given tenant.

    Example::

        class TenantModel(BaseModel):
            organisation = models.ForeignKey("organisations.Organisation", ...)
            objects = ScopedManager()

        # Usage:
        TenantModel.objects.for_scope("organisation", current_org)
    """

    def get_queryset(self) -> ScopedQuerySet:
        return ScopedQuerySet(self.model, using=self._db)

    def for_scope(self, scope_field: str, scope_value) -> ScopedQuerySet:
        """Filter queryset by a scope field and value."""
        return self.get_queryset().for_scope(scope_field, scope_value)

    def active(self) -> ScopedQuerySet:
        """Return only active records (requires is_active field on model)."""
        return self.get_queryset().active()
