"""Django system checks for icv_core."""

from django.apps import apps
from django.core.checks import Error, Tags, Warning, register


@register(Tags.models)
def check_icv_core_configuration(app_configs, **kwargs):
    """Validate icv_core configuration at Django startup."""
    from icv_core.conf import (
        ICV_CORE_ALLOW_HARD_DELETE,
        ICV_CORE_AUDIT_ENABLED,
        ICV_CORE_AUDIT_RETENTION_DAYS,
        ICV_CORE_SOFT_DELETE_FIELD,
        ICV_CORE_UUID_VERSION,
        ICV_TENANCY_TENANT_MODEL,
    )

    errors = []

    # ICV_CORE_UUID_VERSION: must be 4 or 7
    if ICV_CORE_UUID_VERSION not in (4, 7):
        errors.append(
            Error(
                "ICV_CORE_UUID_VERSION must be 4 (random) or 7 (time-sorted).",
                hint=f"Current value: {ICV_CORE_UUID_VERSION}. Set to 4 or 7 in Django settings.",
                id="icv_core.E001",
            )
        )

    # ICV_CORE_SOFT_DELETE_FIELD: must be a non-empty string
    if not isinstance(ICV_CORE_SOFT_DELETE_FIELD, str) or not ICV_CORE_SOFT_DELETE_FIELD.strip():
        errors.append(
            Error(
                "ICV_CORE_SOFT_DELETE_FIELD must be a non-empty string.",
                hint=f"Current value: {ICV_CORE_SOFT_DELETE_FIELD!r}. Set to a valid field name like 'is_active'.",
                id="icv_core.E002",
            )
        )

    # ICV_CORE_AUDIT_RETENTION_DAYS: must be positive when audit is enabled
    if ICV_CORE_AUDIT_ENABLED and (
        not isinstance(ICV_CORE_AUDIT_RETENTION_DAYS, int) or ICV_CORE_AUDIT_RETENTION_DAYS <= 0
    ):
        errors.append(
            Error(
                "ICV_CORE_AUDIT_RETENTION_DAYS must be a positive integer when audit is enabled.",
                hint=f"Current value: {ICV_CORE_AUDIT_RETENTION_DAYS}. Set to a positive number of days.",
                id="icv_core.E003",
            )
        )

    # ICV_CORE_ALLOW_HARD_DELETE: warn if enabled (security risk)
    if ICV_CORE_ALLOW_HARD_DELETE:
        errors.append(
            Warning(
                "ICV_CORE_ALLOW_HARD_DELETE is enabled.",
                hint="Hard deletes bypass soft-delete protection. Ensure this is intentional for your use case.",
                id="icv_core.W001",
            )
        )

    # ICV_TENANCY_TENANT_MODEL: must be a valid model reference
    if ICV_TENANCY_TENANT_MODEL:
        try:
            app_label, model_name = ICV_TENANCY_TENANT_MODEL.split(".")

            # Only validate if apps are ready (models are loaded)
            # This avoids false positives during migrations or early startup
            if apps.ready:
                # Try to get the model (this will fail if model or app doesn't exist)
                try:
                    apps.get_model(app_label, model_name)
                except LookupError:
                    errors.append(
                        Error(
                            f"ICV_TENANCY_TENANT_MODEL references a model that does not exist: {ICV_TENANCY_TENANT_MODEL}",
                            hint="Check that the model name is correct and the app is in INSTALLED_APPS.",
                            id="icv_core.E004",
                        )
                    )
        except ValueError:
            errors.append(
                Error(
                    "ICV_TENANCY_TENANT_MODEL must be in the format 'app_label.ModelName'.",
                    hint=f"Current value: {ICV_TENANCY_TENANT_MODEL!r}. Set to a valid model reference like 'icv_identity.Organisation'.",
                    id="icv_core.E005",
                )
            )

    return errors
