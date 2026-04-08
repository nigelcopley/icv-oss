"""Shared test configuration and fixtures for icv-core."""

import pytest


def pytest_configure(config):
    """Ensure core_testapp is in INSTALLED_APPS when running from the root."""
    from django.conf import settings

    if not settings.configured:
        return
    if "core_testapp" not in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS = [*settings.INSTALLED_APPS, "core_testapp"]
    if not hasattr(settings, "MIGRATION_MODULES"):
        settings.MIGRATION_MODULES = {}
    settings.MIGRATION_MODULES.setdefault("core_testapp", None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def allow_hard_delete(settings):
    """Allow hard deletes on SoftDeleteModel for the duration of a test."""
    settings.ICV_CORE_ALLOW_HARD_DELETE = True
    yield
    settings.ICV_CORE_ALLOW_HARD_DELETE = False


@pytest.fixture
def track_created_by(settings):
    """Enable created_by/updated_by auto-population for the duration of a test."""
    settings.ICV_CORE_TRACK_CREATED_BY = True
    yield
    settings.ICV_CORE_TRACK_CREATED_BY = False
