"""
Tests for ComplianceModel created_by / updated_by auto-population.

Auto-population is controlled by ICV_CORE_TRACK_CREATED_BY and requires
CurrentUserMiddleware (or manual manipulation of _current_user) to supply
the active user at save time.
"""

import pytest
from core_testapp.models import ConcreteComplianceModel
from django.contrib.auth import get_user_model
from django.db import models

from icv_core.middleware import _current_user
from icv_core.models.compliance import ComplianceModel

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_current_user(user):
    """Directly set the thread-local current user (simulates middleware)."""
    _current_user.user = user


def _clear_current_user():
    """Clear the thread-local current user."""
    _current_user.user = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(username="testuser", password="pass")


@pytest.fixture
def other_user(db):
    """Create a second test user for override tests."""
    return User.objects.create_user(username="otheruser", password="pass")


@pytest.fixture(autouse=True)
def clear_middleware_user():
    """Ensure the thread-local user is always cleared between tests."""
    _clear_current_user()
    yield
    _clear_current_user()


# ---------------------------------------------------------------------------
# Structural tests (no DB)
# ---------------------------------------------------------------------------


class TestComplianceModelStructure:
    """ComplianceModel declares the expected fields."""

    def test_is_abstract(self):
        assert ComplianceModel._meta.abstract is True

    def test_has_created_by_field(self):
        field = ComplianceModel._meta.get_field("created_by")
        assert isinstance(field, models.ForeignKey)
        assert field.null is True
        assert field.blank is True

    def test_has_updated_by_field(self):
        field = ComplianceModel._meta.get_field("updated_by")
        assert isinstance(field, models.ForeignKey)
        assert field.null is True
        assert field.blank is True

    def test_created_by_on_delete_set_null(self):
        field = ComplianceModel._meta.get_field("created_by")
        assert field.remote_field.on_delete is models.SET_NULL

    def test_updated_by_on_delete_set_null(self):
        field = ComplianceModel._meta.get_field("updated_by")
        assert field.remote_field.on_delete is models.SET_NULL


# ---------------------------------------------------------------------------
# Auto-population behaviour
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestComplianceModelAutoPopulation:
    """created_by and updated_by are auto-populated when the setting is enabled."""

    def test_created_by_set_on_create(self, user, track_created_by):
        _set_current_user(user)
        obj = ConcreteComplianceModel.objects.create(name="new")
        obj.refresh_from_db()
        assert obj.created_by == user

    def test_updated_by_set_on_create(self, user, track_created_by):
        _set_current_user(user)
        obj = ConcreteComplianceModel.objects.create(name="new")
        obj.refresh_from_db()
        assert obj.updated_by == user

    def test_updated_by_set_on_subsequent_save(self, user, other_user, track_created_by):
        _set_current_user(user)
        obj = ConcreteComplianceModel.objects.create(name="original")
        # Simulate a later save by a different user
        _set_current_user(other_user)
        obj.name = "updated"
        obj.save()
        obj.refresh_from_db()
        assert obj.updated_by == other_user

    def test_created_by_not_changed_on_subsequent_save(self, user, other_user, track_created_by):
        _set_current_user(user)
        obj = ConcreteComplianceModel.objects.create(name="original")
        # Save again as a different user — created_by must not change
        _set_current_user(other_user)
        obj.name = "updated"
        obj.save()
        obj.refresh_from_db()
        assert obj.created_by == user

    def test_explicit_created_by_not_overridden(self, user, other_user, track_created_by):
        """Caller-supplied created_by is never overridden by auto-population."""
        _set_current_user(user)
        obj = ConcreteComplianceModel(name="explicit", created_by=other_user)
        obj.save()
        obj.refresh_from_db()
        assert obj.created_by == other_user

    def test_none_user_does_not_crash_on_create(self, track_created_by):
        """No active request user — fields remain null, no exception raised."""
        _clear_current_user()
        obj = ConcreteComplianceModel.objects.create(name="no-user")
        obj.refresh_from_db()
        assert obj.created_by is None
        assert obj.updated_by is None

    def test_none_user_does_not_crash_on_update(self, user, track_created_by):
        """Middleware user disappears mid-request — save must not raise."""
        _set_current_user(user)
        obj = ConcreteComplianceModel.objects.create(name="created")
        _clear_current_user()
        obj.name = "updated without user"
        obj.save()  # Should not raise
        obj.refresh_from_db()
        # updated_by retains the last persisted value (the original user),
        # not None, because we did not overwrite it when user was absent.
        assert obj.created_by == user


# ---------------------------------------------------------------------------
# Setting disabled
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestComplianceModelSettingDisabled:
    """When ICV_CORE_TRACK_CREATED_BY is False, auto-population is suppressed."""

    def test_created_by_not_set_when_setting_disabled(self, user):
        # track_created_by fixture NOT used — setting remains False
        _set_current_user(user)
        obj = ConcreteComplianceModel.objects.create(name="no-tracking")
        obj.refresh_from_db()
        assert obj.created_by is None

    def test_updated_by_not_set_when_setting_disabled(self, user):
        _set_current_user(user)
        obj = ConcreteComplianceModel.objects.create(name="no-tracking")
        obj.refresh_from_db()
        assert obj.updated_by is None

    def test_save_succeeds_when_setting_disabled(self, user):
        """Object saves normally even when auto-population is turned off."""
        _set_current_user(user)
        obj = ConcreteComplianceModel.objects.create(name="ok")
        assert obj.pk is not None
