from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class IcvCoreConfig(AppConfig):
    name = "icv_core"
    label = "icv_core"
    verbose_name = _("ICV Core")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from icv_core.conf import ICV_CORE_AUDIT_ENABLED

        from . import (
            checks,  # noqa: F401 — register system checks
            handlers,  # noqa: F401 — connect signal handlers
        )

        if ICV_CORE_AUDIT_ENABLED:
            from icv_core.audit import handlers as audit_handlers  # noqa: F401
