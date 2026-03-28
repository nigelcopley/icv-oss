"""
pytest fixtures for icv-core.

Import in your conftest.py::

    from icv_core.testing.fixtures import *  # noqa: F401,F403
"""

import pytest


@pytest.fixture
def audit_enabled(settings):
    """Enable the audit subsystem for a single test."""
    settings.ICV_CORE_AUDIT_ENABLED = True
    yield
    settings.ICV_CORE_AUDIT_ENABLED = False


@pytest.fixture
def allow_hard_delete(settings):
    """Allow hard deletes on SoftDeleteModel for a single test."""
    settings.ICV_CORE_ALLOW_HARD_DELETE = True
    yield
    settings.ICV_CORE_ALLOW_HARD_DELETE = False
