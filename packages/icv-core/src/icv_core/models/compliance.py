"""ComplianceModel with created_by/updated_by user attribution tracking."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from icv_core.models.base import BaseModel


class ComplianceModel(BaseModel):
    """
    Abstract model adding created_by and updated_by user attribution fields.

    Requires ICV_CORE_TRACK_CREATED_BY=True and CurrentUserMiddleware to
    automatically populate these fields on save.

    When middleware is not present (e.g., management commands, Celery tasks),
    both fields remain null. Consuming code should populate them explicitly
    in those contexts.

    Auto-population behaviour
    -------------------------
    - ``created_by`` is populated on INSERT only, and only when it has not
      been set explicitly by the caller.
    - ``updated_by`` is populated on every save (INSERT and UPDATE).
    - Both fields are left untouched when ICV_CORE_TRACK_CREATED_BY is False
      or when ``get_current_user()`` returns None (no active request).
    - Explicitly set values are never overridden.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("created by"),
        help_text=_("User who created this record."),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("updated by"),
        help_text=_("User who last updated this record."),
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs) -> None:
        """
        Override save to auto-populate created_by and updated_by.

        Uses get_setting() at call time (not import time) so that the
        ICV_CORE_TRACK_CREATED_BY pytest ``settings`` fixture override is
        respected during tests.
        """
        from icv_core.conf import get_setting
        from icv_core.middleware import get_current_user

        if get_setting("TRACK_CREATED_BY", False):
            user = get_current_user()
            if user is not None:
                if self._state.adding and self.created_by_id is None:
                    self.created_by = user
                self.updated_by = user

        super().save(*args, **kwargs)
