"""Manager and QuerySet for soft-delete filtering."""

from django.db import models


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet that filters soft-deleted records."""

    def active(self) -> "SoftDeleteQuerySet":
        """Return only active (non-deleted) records."""
        return self.filter(is_active=True)

    def deleted(self) -> "SoftDeleteQuerySet":
        """Return only soft-deleted records."""
        return self.filter(is_active=False)

    def with_deleted(self) -> "SoftDeleteQuerySet":
        """Return all records, including soft-deleted ones."""
        return self.all()


class SoftDeleteManager(models.Manager):
    """
    Default manager for SoftDeleteModel.

    Excludes soft-deleted records from all default queries. Use
    `Model.all_objects` for unfiltered access.
    """

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_active=True)

    def active(self) -> SoftDeleteQuerySet:
        """Return only active records (alias for default queryset)."""
        return self.get_queryset()

    def deleted(self) -> SoftDeleteQuerySet:
        """Return only soft-deleted records."""
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_active=False)

    def with_deleted(self) -> SoftDeleteQuerySet:
        """Return all records including soft-deleted ones."""
        return SoftDeleteQuerySet(self.model, using=self._db)
