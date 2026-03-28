"""AppConfig for taxonomy_testapp."""

from __future__ import annotations

from django.apps import AppConfig


class TaxonomyTestAppConfig(AppConfig):
    name = "taxonomy_testapp"
    label = "taxonomy_testapp"
    verbose_name = "Taxonomy Test App"
    default_auto_field = "django.db.models.BigAutoField"
