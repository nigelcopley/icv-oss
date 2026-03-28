"""
AuditMixin — adds automatic audit logging on model save and delete.

Add to any concrete model to automatically record audit entries::

    from icv_core.audit.mixins import AuditMixin

    class MyModel(AuditMixin, BaseModel):
        name = models.CharField(max_length=255)

When ICV_CORE_AUDIT_TRACK_FIELD_CHANGES=True the mixin captures field values
before save and includes a ``changed_fields`` dict in the audit entry metadata.

Audit logging is a no-op when ICV_CORE_AUDIT_ENABLED=False. Failures are
caught and logged so that audit errors never interrupt model saves or deletes.
"""

import logging

from django.db import models

logger = logging.getLogger(__name__)


class AuditMixin(models.Model):
    """
    Abstract mixin that records audit entries on save and delete.

    Must appear before the base model in the MRO::

        class MyModel(AuditMixin, BaseModel):
            ...
    """

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pre_save_state: dict = {}

    def save(self, *args, **kwargs) -> None:
        from icv_core.conf import get_setting

        is_new = self.pk is None

        if not is_new and get_setting("AUDIT_TRACK_FIELD_CHANGES", True):
            self._pre_save_state = self._capture_field_state()

        super().save(*args, **kwargs)
        self._emit_save_audit(is_new=is_new)

    def delete(self, *args, **kwargs):
        self._emit_delete_audit()
        return super().delete(*args, **kwargs)

    def _capture_field_state(self) -> dict:
        """Capture current field values for change tracking."""
        return {
            field.name: getattr(self, field.name)
            for field in self._meta.fields
            if field.name not in ("id", "created_at", "updated_at")
        }

    def _emit_save_audit(self, is_new: bool) -> None:
        """Record an audit entry after a successful save.

        Creates a DATA/CREATE entry for new instances or DATA/UPDATE for
        existing ones. When ICV_CORE_AUDIT_TRACK_FIELD_CHANGES is True, a
        ``changed_fields`` dict is included in the entry metadata.
        """
        from icv_core.audit.services import log_event
        from icv_core.conf import get_setting

        try:
            action = "CREATE" if is_new else "UPDATE"
            metadata: dict = {}

            if not is_new and get_setting("AUDIT_TRACK_FIELD_CHANGES", True) and self._pre_save_state:
                current_state = self._capture_field_state()
                changed = {
                    k: {"old": str(self._pre_save_state.get(k)), "new": str(v)}
                    for k, v in current_state.items()
                    if self._pre_save_state.get(k) != v
                }
                if changed:
                    metadata["changed_fields"] = changed

            log_event(
                event_type="DATA",
                action=action,
                target=self,
                description=f"{self._meta.label} {action.lower()}d: {self!s}",
                metadata=metadata,
            )
        except Exception:
            logger.exception(
                "Audit logging failed for %s.save (pk=%s)",
                self._meta.label,
                self.pk,
            )

    def _emit_delete_audit(self) -> None:
        """Record an audit entry before a delete.

        Creates a DATA/DELETE entry. Called before the actual delete so that
        ``self`` is still available as the audit target.
        """
        from icv_core.audit.services import log_event

        try:
            log_event(
                event_type="DATA",
                action="DELETE",
                target=self,
                description=f"{self._meta.label} deleted: {self!s}",
                metadata={},
            )
        except Exception:
            logger.exception(
                "Audit logging failed for %s.delete (pk=%s)",
                self._meta.label,
                self.pk,
            )
