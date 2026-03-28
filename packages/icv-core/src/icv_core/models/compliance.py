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
