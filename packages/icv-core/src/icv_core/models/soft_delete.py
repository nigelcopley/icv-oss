"""Soft-delete abstract model with custom manager and lifecycle signals."""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from icv_core.managers.soft_delete import SoftDeleteManager
from icv_core.models.base import BaseModel


class SoftDeleteModel(BaseModel):
    """
    Abstract model with soft-delete support.

    Records are never hard-deleted by default. Calling soft_delete() sets
    is_active=False and records the deletion timestamp. The default manager
    excludes soft-deleted records; use all_objects to include them.

    Hard deletion is blocked unless ICV_CORE_ALLOW_HARD_DELETE=True. Use
    hard_delete() for permanent removal when required.
    """

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("active"),
        help_text=_("Unselect to soft-delete this record."),
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("deleted at"),
        help_text=_("Set automatically by soft_delete(). Null if the record is active."),
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self) -> None:
        """Mark this record as soft-deleted."""
        from icv_core.signals import post_soft_delete, pre_soft_delete

        pre_soft_delete.send(sender=self.__class__, instance=self)
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at", "updated_at"])
        post_soft_delete.send(sender=self.__class__, instance=self)

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        from icv_core.signals import post_restore, pre_restore

        pre_restore.send(sender=self.__class__, instance=self)
        self.is_active = True
        self.deleted_at = None
        self.save(update_fields=["is_active", "deleted_at", "updated_at"])
        post_restore.send(sender=self.__class__, instance=self)

    def delete(self, using=None, keep_parents=False):
        """
        Override delete() to prevent accidental hard deletes.

        Raises ProtectedError unless ICV_CORE_ALLOW_HARD_DELETE=True.
        Use soft_delete() for safe deletion or hard_delete() for permanent removal.
        """
        from icv_core.conf import get_setting

        if get_setting("ALLOW_HARD_DELETE", False):
            return super().delete(using=using, keep_parents=keep_parents)
        raise models.ProtectedError(
            "Hard delete is not allowed on SoftDeleteModel. Use soft_delete() or set ICV_CORE_ALLOW_HARD_DELETE=True.",
            {self},
        )

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete this record from the database, bypassing soft-delete protection."""
        return super().delete(using=using, keep_parents=keep_parents)
