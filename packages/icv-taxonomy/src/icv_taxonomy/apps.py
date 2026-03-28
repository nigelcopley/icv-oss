"""AppConfig for icv-taxonomy."""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class IcvTaxonomyConfig(AppConfig):
    name = "icv_taxonomy"
    label = "icv_taxonomy"
    verbose_name = _("ICV Taxonomy")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Connect signal handlers and register system checks at startup."""
        from . import (  # noqa: F401 — registers system checks  # noqa: F401 — connects post_save/pre_delete handlers
            checks,
            handlers,
        )

        # Conditionally bridge icv_tree.signals.node_moved → term_moved.
        # Skipped silently when icv-tree is not installed.
        handlers._connect_node_moved_handler()
