"""
Test helper functions for icv-core.

Utility functions to assist testing code that uses icv-core's base models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from icv_core.models.soft_delete import SoftDeleteModel


def assert_soft_deleted(instance: SoftDeleteModel) -> None:
    """Assert that a SoftDeleteModel instance has been soft-deleted."""
    instance.refresh_from_db()
    assert not instance.is_active, f"Expected {instance!r} to be soft-deleted but is_active={instance.is_active}"
    assert instance.deleted_at is not None, f"Expected {instance!r} to have deleted_at set"


def assert_restored(instance: SoftDeleteModel) -> None:
    """Assert that a SoftDeleteModel instance has been restored."""
    instance.refresh_from_db()
    assert instance.is_active, f"Expected {instance!r} to be active but is_active={instance.is_active}"
    assert instance.deleted_at is None, f"Expected {instance!r} to have deleted_at=None"
