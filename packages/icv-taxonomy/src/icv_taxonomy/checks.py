"""
System checks for icv-taxonomy.

Registered automatically by IcvTaxonomyConfig.ready() via import.
"""

from __future__ import annotations

from django.core.checks import Error, register


@register()
def check_vocabulary_model(app_configs, **kwargs):  # type: ignore[no-untyped-def]
    """Validate ICV_TAXONOMY_VOCABULARY_MODEL points to a valid model (icv_taxonomy.E001)."""
    from .conf import get_setting

    errors = []
    model_string = get_setting("ICV_TAXONOMY_VOCABULARY_MODEL", "icv_taxonomy.Vocabulary")

    if not isinstance(model_string, str) or "." not in model_string:
        errors.append(
            Error(
                f"ICV_TAXONOMY_VOCABULARY_MODEL must be a dotted 'app_label.ModelName' string. Got: {model_string!r}",
                id="icv_taxonomy.E001",
            )
        )

    return errors


@register()
def check_term_model(app_configs, **kwargs):  # type: ignore[no-untyped-def]
    """Validate ICV_TAXONOMY_TERM_MODEL points to a valid model (icv_taxonomy.E002)."""
    from .conf import get_setting

    errors = []
    model_string = get_setting("ICV_TAXONOMY_TERM_MODEL", "icv_taxonomy.Term")

    if not isinstance(model_string, str) or "." not in model_string:
        errors.append(
            Error(
                f"ICV_TAXONOMY_TERM_MODEL must be a dotted 'app_label.ModelName' string. Got: {model_string!r}",
                id="icv_taxonomy.E002",
            )
        )

    return errors
