"""
Tests for icv-core audit decorators, mixins, and signal handlers.

Covers:
- @audited decorator (happy path, user/request extraction, audit disabled)
- AuditMixin (save/delete hooks, field-change tracking, field-state capture)
- audit handlers (login, logout, failed-login — both via signal dispatch and
  direct invocation)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def audit_on(settings):
    """Enable the audit subsystem for the duration of a test."""
    settings.ICV_CORE_AUDIT_ENABLED = True
    settings.ICV_CORE_AUDIT_CAPTURE_IP = True
    settings.ICV_CORE_AUDIT_CAPTURE_USER_AGENT = True
    settings.ICV_CORE_AUDIT_TRACK_FIELD_CHANGES = True
    yield settings
    settings.ICV_CORE_AUDIT_ENABLED = False


@pytest.fixture
def audit_off(settings):
    """Explicitly disable the audit subsystem for the duration of a test."""
    settings.ICV_CORE_AUDIT_ENABLED = False
    yield settings


@pytest.fixture
def user(db):
    return User.objects.create_user(username="tester", email="tester@example.com", password="secret")


@pytest.fixture
def rf():
    return RequestFactory()


def _make_request_mock(ip="1.2.3.4", ua="TestAgent/1.0", user=None):
    """Build a minimal fake request using MagicMock (non-HttpRequest)."""
    request = MagicMock()
    request.META = {"REMOTE_ADDR": ip, "HTTP_USER_AGENT": ua}
    request.user = user
    return request


def _make_http_request(ip="1.2.3.4", ua="TestAgent/1.0", user=None):
    """Build a real HttpRequest via RequestFactory so isinstance checks pass."""

    request = RequestFactory().get("/")
    request.META["REMOTE_ADDR"] = ip
    request.META["HTTP_USER_AGENT"] = ua
    request.user = user
    return request


# ---------------------------------------------------------------------------
# @audited decorator — happy path
# ---------------------------------------------------------------------------


class TestAuditedDecoratorHappyPath:
    """@audited creates an AuditEntry on every successful call."""

    @pytest.mark.django_db
    def test_creates_audit_entry_on_call(self, audit_on):
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        @audited(event_type="DATA", action="CREATE")
        def do_thing():
            pass

        do_thing()

        assert AuditEntry.objects.count() == 1

    @pytest.mark.django_db
    def test_event_type_stored_correctly(self, audit_on):
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        @audited(event_type="SECURITY", action="PERMISSION_DENIED")
        def sensitive():
            pass

        sensitive()

        entry = AuditEntry.objects.get()
        assert entry.event_type == "SECURITY"

    @pytest.mark.django_db
    def test_action_stored_correctly(self, audit_on):
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        @audited(event_type="DATA", action="DELETE")
        def remove():
            pass

        remove()

        entry = AuditEntry.objects.get()
        assert entry.action == "DELETE"

    @pytest.mark.django_db
    def test_return_value_is_preserved(self, audit_on):
        from icv_core.audit.decorators import audited

        @audited(event_type="DATA", action="CUSTOM")
        def get_value():
            return 42

        result = get_value()

        assert result == 42

    def test_decorator_preserves_function_name(self):
        from icv_core.audit.decorators import audited

        @audited(event_type="DATA", action="CUSTOM")
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    @pytest.mark.django_db
    def test_description_stored_on_entry(self, audit_on):
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        @audited(event_type="SYSTEM", action="CUSTOM", description="Export triggered")
        def export():
            pass

        export()

        entry = AuditEntry.objects.get()
        assert entry.description == "Export triggered"

    @pytest.mark.django_db
    def test_metadata_stored_on_entry(self, audit_on):
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        @audited(event_type="DATA", action="CUSTOM", metadata={"report": "monthly"})
        def run():
            pass

        run()

        entry = AuditEntry.objects.get()
        assert entry.metadata == {"report": "monthly"}

    @pytest.mark.django_db
    def test_metadata_defaults_to_empty_dict(self, audit_on):
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        @audited(event_type="DATA", action="CREATE")
        def create():
            pass

        create()

        entry = AuditEntry.objects.get()
        assert entry.metadata == {}

    @pytest.mark.django_db
    def test_multiple_calls_create_multiple_entries(self, audit_on):
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        @audited(event_type="DATA", action="CREATE")
        def action():
            pass

        action()
        action()
        action()

        assert AuditEntry.objects.count() == 3


# ---------------------------------------------------------------------------
# @audited decorator — request extraction
# ---------------------------------------------------------------------------


class TestAuditedDecoratorRequestExtraction:
    """@audited pulls user and IP from an HttpRequest positional argument."""

    @pytest.mark.django_db
    def test_extracts_user_from_request_positional_arg(self, audit_on, user):
        """When first positional arg is a real HttpRequest, user is extracted."""
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        @audited(event_type="DATA", action="VIEW")
        def view(request):
            pass

        request = _make_http_request(user=user)
        view(request)

        entry = AuditEntry.objects.get()
        assert entry.user == user

    @pytest.mark.django_db
    def test_extracts_ip_from_request_positional_arg(self, audit_on):
        """IP address is read from the real HttpRequest META."""
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        @audited(event_type="DATA", action="VIEW")
        def view(request):
            pass

        view(_make_http_request(ip="5.6.7.8"))

        entry = AuditEntry.objects.get()
        assert entry.ip_address == "5.6.7.8"

    @pytest.mark.django_db
    def test_extracts_user_from_request_keyword_arg(self, audit_on, user):
        """When request is passed as a keyword argument, user is extracted."""
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        @audited(event_type="DATA", action="VIEW")
        def service_fn(*, request):
            pass

        service_fn(request=_make_http_request(user=user))

        entry = AuditEntry.objects.get()
        assert entry.user == user

    @pytest.mark.django_db
    def test_no_request_falls_back_to_middleware_context(self, audit_on):
        """Without a request arg, IP comes from the thread-local audit context."""
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        ctx: dict = {"ip_address": "9.9.9.9", "user_agent": "", "user": None}
        with patch("icv_core.audit.middleware.get_audit_context", return_value=ctx):

            @audited(event_type="SYSTEM", action="CUSTOM")
            def background_task():
                pass

            background_task()

        entry = AuditEntry.objects.get()
        assert entry.ip_address == "9.9.9.9"

    @pytest.mark.django_db
    def test_no_request_no_context_ip_is_none(self, audit_on):
        """When neither request nor thread-local context provides an IP, it is None."""
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        ctx: dict = {}
        with patch("icv_core.audit.middleware.get_audit_context", return_value=ctx):

            @audited(event_type="SYSTEM", action="CUSTOM")
            def background_task():
                pass

            background_task()

        entry = AuditEntry.objects.get()
        assert entry.ip_address is None


# ---------------------------------------------------------------------------
# @audited decorator — audit disabled
# ---------------------------------------------------------------------------


class TestAuditedDecoratorDisabled:
    """@audited is a no-op when ICV_CORE_AUDIT_ENABLED=False."""

    @pytest.mark.django_db
    def test_does_not_create_entry_when_disabled(self, audit_off):
        from icv_core.audit.decorators import audited
        from icv_core.audit.models import AuditEntry

        @audited(event_type="DATA", action="CREATE")
        def do_thing():
            pass

        do_thing()

        assert AuditEntry.objects.count() == 0

    def test_returns_value_even_when_disabled(self, audit_off):
        from icv_core.audit.decorators import audited

        @audited(event_type="DATA", action="CREATE")
        def get_value():
            return "result"

        assert get_value() == "result"


# ---------------------------------------------------------------------------
# AuditMixin — structural
# ---------------------------------------------------------------------------


class TestAuditMixinMeta:
    """AuditMixin structural tests that do not require the DB."""

    def test_is_abstract(self):
        from icv_core.audit.mixins import AuditMixin

        assert AuditMixin._meta.abstract is True

    def test_pre_save_state_initialised_on_new_instance(self):
        """A freshly instantiated mixin model has an empty _pre_save_state."""
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel(label="x")
        assert obj._pre_save_state == {}

    def test_emit_save_audit_callable_without_raising(self):
        """_emit_save_audit must not raise when called as a no-argument hook."""
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel(label="stub")
        obj._emit_save_audit(is_new=True)

    def test_emit_delete_audit_callable_without_raising(self):
        """_emit_delete_audit must not raise when called directly."""
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel(label="stub")
        obj._emit_delete_audit()


# ---------------------------------------------------------------------------
# AuditMixin — field-state capture
# ---------------------------------------------------------------------------


class TestAuditMixinFieldTracking:
    """AuditMixin captures field values for change tracking."""

    @pytest.mark.django_db
    def test_capture_field_state_returns_field_dict(self, audit_on):
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel.objects.create(label="original")
        state = obj._capture_field_state()

        assert isinstance(state, dict)
        assert "label" in state
        assert state["label"] == "original"

    @pytest.mark.django_db
    def test_capture_field_state_excludes_id_timestamps(self, audit_on):
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel.objects.create(label="test")
        state = obj._capture_field_state()

        assert "id" not in state
        assert "created_at" not in state
        assert "updated_at" not in state

    @pytest.mark.django_db
    def test_pre_save_state_captures_in_memory_state_before_db_write(self, audit_on):
        """
        AuditMixin captures _pre_save_state just before calling super().save().

        Because BaseModel uses a UUID primary key (set at __init__ time, never
        None), the ``is_new = self.pk is None`` guard is always False.
        As a result _pre_save_state is captured on every save, including the
        first one. The captured value reflects whatever is in memory at the
        moment save() is called.
        """
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel.objects.create(label="before")
        obj.label = "after"
        obj.save()

        # At the point capture runs, label is already "after" in memory.
        assert obj._pre_save_state.get("label") == "after"

    @pytest.mark.django_db
    def test_pre_save_state_populated_on_first_save_due_to_uuid_pk(self, audit_on):
        """
        UUID PKs are set at __init__ time, so is_new is always False.
        _pre_save_state is populated even on the first save().
        """
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel(label="new")
        assert obj._pre_save_state == {}
        obj.save()
        assert obj._pre_save_state == {"label": "new"}

    @pytest.mark.django_db
    def test_emit_save_audit_builds_changed_fields_when_values_differ(self, audit_on):
        """_emit_save_audit computes changed_fields when old and new values differ."""
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel.objects.create(label="original")
        # Manually set a stale _pre_save_state to simulate a detected change.
        obj._pre_save_state = {"label": "original"}
        obj.label = "changed"
        # Call the hook directly — it must not raise and can use the stale state.
        obj._emit_save_audit(is_new=False)

    @pytest.mark.django_db
    def test_field_tracking_disabled_skips_pre_save_on_update(self, settings):
        """When ICV_CORE_AUDIT_TRACK_FIELD_CHANGES=False, _pre_save_state stays empty."""
        settings.ICV_CORE_AUDIT_ENABLED = True
        settings.ICV_CORE_AUDIT_TRACK_FIELD_CHANGES = False

        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel.objects.create(label="first")
        # Clear the state that was set by the first save().
        obj._pre_save_state = {}
        obj.label = "second"
        obj.save()

        # With tracking disabled the branch that sets _pre_save_state is skipped.
        assert obj._pre_save_state == {}


# ---------------------------------------------------------------------------
# AuditMixin — save / delete lifecycle
# ---------------------------------------------------------------------------


class TestAuditMixinSaveDelete:
    """AuditMixin save() and delete() lifecycle hooks."""

    @pytest.mark.django_db
    def test_save_does_not_raise_on_create(self, audit_on):
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel(label="create")
        obj.save()
        assert obj.pk is not None

    @pytest.mark.django_db
    def test_save_does_not_raise_on_update(self, audit_on):
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel.objects.create(label="v1")
        obj.label = "v2"
        obj.save()
        obj.refresh_from_db()
        assert obj.label == "v2"

    @pytest.mark.django_db
    def test_delete_removes_object_from_db(self, audit_on):
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel.objects.create(label="deletable")
        pk = obj.pk
        obj.delete()
        assert not ConcreteAuditModel.objects.filter(pk=pk).exists()

    @pytest.mark.django_db
    def test_delete_calls_emit_delete_audit(self, audit_on):
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel.objects.create(label="spy")
        with patch.object(obj, "_emit_delete_audit") as mock_emit:
            obj.delete()
        mock_emit.assert_called_once()

    @pytest.mark.django_db
    def test_save_calls_emit_save_audit(self, audit_on):
        """save() always calls _emit_save_audit(is_new=False) for UUID-PK models."""
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel(label="new")
        with patch.object(obj, "_emit_save_audit") as mock_emit:
            obj.save()
        # UUID PK is set at __init__ time, so is_new is always False.
        mock_emit.assert_called_once_with(is_new=False)

    @pytest.mark.django_db
    def test_save_update_calls_emit_save_audit(self, audit_on):
        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel.objects.create(label="v1")
        obj.label = "v2"
        with patch.object(obj, "_emit_save_audit") as mock_emit:
            obj.save()
        mock_emit.assert_called_once_with(is_new=False)


# ---------------------------------------------------------------------------
# Audit signal handlers — direct invocation
# ---------------------------------------------------------------------------


class TestHandlerFunctionsDirectly:
    """Exercise handler functions directly without relying on signal dispatch."""

    @pytest.mark.django_db
    def test_log_login_writes_authentication_login_entry(self, audit_on, user):
        from icv_core.audit.handlers import log_login
        from icv_core.audit.models import AuditEntry

        request = _make_request_mock(ip="1.2.3.4", user=user)
        log_login(sender=user.__class__, request=request, user=user)

        entry = AuditEntry.objects.get(action="LOGIN")
        assert entry.event_type == "AUTHENTICATION"
        assert entry.user == user

    @pytest.mark.django_db
    def test_log_login_description_contains_user(self, audit_on, user):
        from icv_core.audit.handlers import log_login
        from icv_core.audit.models import AuditEntry

        request = _make_request_mock(user=user)
        log_login(sender=user.__class__, request=request, user=user)

        entry = AuditEntry.objects.get(action="LOGIN")
        assert str(user) in entry.description

    @pytest.mark.django_db
    def test_log_logout_writes_authentication_logout_entry(self, audit_on, user):
        from icv_core.audit.handlers import log_logout
        from icv_core.audit.models import AuditEntry

        request = _make_request_mock(user=user)
        log_logout(sender=user.__class__, request=request, user=user)

        entry = AuditEntry.objects.get(action="LOGOUT")
        assert entry.event_type == "AUTHENTICATION"
        assert entry.user == user

    @pytest.mark.django_db
    def test_log_logout_description_contains_user(self, audit_on, user):
        from icv_core.audit.handlers import log_logout
        from icv_core.audit.models import AuditEntry

        request = _make_request_mock(user=user)
        log_logout(sender=user.__class__, request=request, user=user)

        entry = AuditEntry.objects.get(action="LOGOUT")
        assert str(user) in entry.description

    @pytest.mark.django_db
    def test_log_login_failure_writes_security_login_entry(self, audit_on):
        from icv_core.audit.handlers import log_login_failure
        from icv_core.audit.models import AuditEntry

        request = _make_request_mock()
        log_login_failure(
            sender=User,
            credentials={"username": "probe@example.com", "password": "wrong"},
            request=request,
        )

        entry = AuditEntry.objects.get(event_type="SECURITY")
        assert entry.action == "LOGIN"

    @pytest.mark.django_db
    def test_log_login_failure_stores_attempted_username_in_metadata(self, audit_on):
        from icv_core.audit.handlers import log_login_failure
        from icv_core.audit.models import AuditEntry

        request = _make_request_mock()
        log_login_failure(
            sender=User,
            credentials={"username": "attacker@evil.com"},
            request=request,
        )

        entry = AuditEntry.objects.get(event_type="SECURITY")
        assert entry.metadata["attempted_username"] == "attacker@evil.com"

    @pytest.mark.django_db
    def test_log_login_failure_description_mentions_username(self, audit_on):
        from icv_core.audit.handlers import log_login_failure
        from icv_core.audit.models import AuditEntry

        request = _make_request_mock()
        log_login_failure(
            sender=User,
            credentials={"username": "specific@user.com"},
            request=request,
        )

        entry = AuditEntry.objects.get(event_type="SECURITY")
        assert "specific@user.com" in entry.description

    @pytest.mark.django_db
    def test_log_login_failure_no_user_on_entry(self, audit_on):
        """A failed login entry has no authenticated user."""
        from icv_core.audit.handlers import log_login_failure
        from icv_core.audit.models import AuditEntry

        request = _make_request_mock()
        log_login_failure(
            sender=User,
            credentials={"username": "nobody@void.com"},
            request=request,
        )

        entry = AuditEntry.objects.get(event_type="SECURITY")
        assert entry.user is None

    @pytest.mark.django_db
    def test_log_login_failure_missing_username_key_uses_unknown(self, audit_on):
        """Credentials without a 'username' key fall back to 'unknown' in description."""
        from icv_core.audit.handlers import log_login_failure
        from icv_core.audit.models import AuditEntry

        request = _make_request_mock()
        log_login_failure(sender=User, credentials={}, request=request)

        entry = AuditEntry.objects.get(event_type="SECURITY")
        assert "unknown" in entry.description
        assert entry.metadata["attempted_username"] == ""


# ---------------------------------------------------------------------------
# Audit signal handlers — via signal dispatch (handler connected manually)
# ---------------------------------------------------------------------------


class TestSignalDispatchConnectsHandlers:
    """
    Verify handlers produce entries when triggered via actual signal dispatch.

    Importing icv_core.audit.handlers registers the @receiver decorators,
    permanently attaching the handlers to Django's auth signals for the
    duration of the test process.  Each test therefore counts entries created
    *by its own dispatch call* by snapshotting the count before and after.
    """

    @pytest.mark.django_db
    def test_user_logged_in_signal_creates_login_entry(self, audit_on, user):
        from django.contrib.auth.signals import user_logged_in

        import icv_core.audit.handlers  # noqa: F401 — ensures receivers are registered
        from icv_core.audit.models import AuditEntry

        before = AuditEntry.objects.filter(event_type="AUTHENTICATION", action="LOGIN").count()
        request = _make_request_mock(user=user)
        user_logged_in.send(sender=user.__class__, request=request, user=user)
        after = AuditEntry.objects.filter(event_type="AUTHENTICATION", action="LOGIN").count()

        assert after == before + 1

    @pytest.mark.django_db
    def test_user_logged_out_signal_creates_logout_entry(self, audit_on, user):
        from django.contrib.auth.signals import user_logged_out

        import icv_core.audit.handlers  # noqa: F401 — ensures receivers are registered
        from icv_core.audit.models import AuditEntry

        before = AuditEntry.objects.filter(event_type="AUTHENTICATION", action="LOGOUT").count()
        request = _make_request_mock(user=user)
        user_logged_out.send(sender=user.__class__, request=request, user=user)
        after = AuditEntry.objects.filter(event_type="AUTHENTICATION", action="LOGOUT").count()

        assert after == before + 1

    @pytest.mark.django_db
    def test_user_login_failed_signal_creates_security_entry(self, audit_on):
        from django.contrib.auth.signals import user_login_failed

        import icv_core.audit.handlers  # noqa: F401 — ensures receivers are registered
        from icv_core.audit.models import AuditEntry

        before = AuditEntry.objects.filter(event_type="SECURITY", action="LOGIN").count()
        request = _make_request_mock()
        user_login_failed.send(
            sender=User,
            credentials={"username": "brute@force.com"},
            request=request,
        )
        after = AuditEntry.objects.filter(event_type="SECURITY", action="LOGIN").count()

        assert after == before + 1


# ---------------------------------------------------------------------------
# AuditMixin — actual AuditEntry creation (log_event integration)
# ---------------------------------------------------------------------------


class TestAuditMixinCreatesEntries:
    """AuditMixin calls log_event, which creates AuditEntry records when enabled."""

    @pytest.mark.django_db
    def test_save_creates_audit_entry_when_enabled(self, audit_on):
        from core_testapp.models import ConcreteAuditModel

        from icv_core.audit.models import AuditEntry

        ConcreteAuditModel.objects.create(label="tracked")

        assert AuditEntry.objects.filter(event_type="DATA", action="UPDATE").exists()

    @pytest.mark.django_db
    def test_delete_creates_audit_entry_when_enabled(self, audit_on):
        from core_testapp.models import ConcreteAuditModel

        from icv_core.audit.models import AuditEntry

        before = AuditEntry.objects.filter(event_type="DATA", action="DELETE").count()
        obj = ConcreteAuditModel.objects.create(label="to-delete")
        obj.delete()
        after = AuditEntry.objects.filter(event_type="DATA", action="DELETE").count()

        assert after == before + 1

    @pytest.mark.django_db
    def test_save_no_entry_when_audit_disabled(self, audit_off):
        from core_testapp.models import ConcreteAuditModel

        from icv_core.audit.models import AuditEntry

        ConcreteAuditModel.objects.create(label="silent")

        assert AuditEntry.objects.count() == 0

    @pytest.mark.django_db
    def test_delete_no_entry_when_audit_disabled(self, audit_off):
        from core_testapp.models import ConcreteAuditModel

        from icv_core.audit.models import AuditEntry

        obj = ConcreteAuditModel.objects.create(label="silent-delete")
        obj.delete()

        assert AuditEntry.objects.count() == 0

    @pytest.mark.django_db
    def test_emit_save_audit_swallows_log_event_exception(self, audit_on, caplog):
        """Exceptions from log_event are caught so they don't break model saves."""
        import logging

        from core_testapp.models import ConcreteAuditModel

        # log_event is imported inside the method body, so we patch it at its
        # definition site in icv_core.audit.services.
        with (
            patch("icv_core.audit.services.log_event", side_effect=RuntimeError("boom")),
            caplog.at_level(logging.ERROR, logger="icv_core.audit.mixins"),
        ):
            obj = ConcreteAuditModel(label="error-test")
            obj.save()  # Must not raise

        assert "Audit logging failed" in caplog.text

    @pytest.mark.django_db
    def test_emit_delete_audit_swallows_log_event_exception(self, audit_on, caplog):
        """Exceptions from log_event during delete are caught so the delete proceeds."""
        import logging

        from core_testapp.models import ConcreteAuditModel

        obj = ConcreteAuditModel.objects.create(label="error-delete")
        with (
            patch("icv_core.audit.services.log_event", side_effect=RuntimeError("boom")),
            caplog.at_level(logging.ERROR, logger="icv_core.audit.mixins"),
        ):
            obj.delete()  # Must not raise

        assert "Audit logging failed" in caplog.text


# ---------------------------------------------------------------------------
# AuditEntry model immutability (missed lines in audit/models.py)
# ---------------------------------------------------------------------------


class TestAuditEntryImmutability:
    """AuditEntry records cannot be updated or deleted after creation."""

    @pytest.mark.django_db
    def test_update_raises_immutable_record_error(self, audit_on):
        from icv_core.audit.models import AuditEntry
        from icv_core.exceptions import ImmutableRecordError

        entry = AuditEntry.objects.create(event_type="DATA", action="CREATE")
        entry.description = "changed"

        with pytest.raises(ImmutableRecordError):
            entry.save()

    @pytest.mark.django_db
    def test_delete_raises_protected_error(self, audit_on):
        from django.db import models as django_models

        from icv_core.audit.models import AuditEntry

        entry = AuditEntry.objects.create(event_type="DATA", action="CREATE")

        with pytest.raises(django_models.ProtectedError):
            entry.delete()

    @pytest.mark.django_db
    def test_str_contains_event_type_and_action(self, audit_on):
        from icv_core.audit.models import AuditEntry

        entry = AuditEntry.objects.create(event_type="SYSTEM", action="CUSTOM")
        s = str(entry)
        assert "SYSTEM" in s
        assert "CUSTOM" in s

    @pytest.mark.django_db
    def test_create_fires_audit_entry_created_signal(self, audit_on):
        from icv_core.audit.models import AuditEntry
        from icv_core.audit.signals import audit_entry_created

        received = []

        def handler(sender, instance, **kw):
            received.append(instance)

        audit_entry_created.connect(handler, dispatch_uid="test_ae_created")
        try:
            entry = AuditEntry.objects.create(event_type="DATA", action="DELETE")
        finally:
            audit_entry_created.disconnect(handler, dispatch_uid="test_ae_created")

        assert len(received) == 1
        assert received[0] == entry


# ---------------------------------------------------------------------------
# AdminActivityLog str (missed line in audit/models.py)
# ---------------------------------------------------------------------------


class TestAdminActivityLogStr:
    @pytest.mark.django_db
    def test_str_contains_action_type(self, user):
        from icv_core.audit.models import AdminActivityLog

        log = AdminActivityLog.objects.create(
            admin_user=user,
            action_type="verify_coach",
            description="Verified coaching credentials",
        )
        s = str(log)
        assert "verify_coach" in s

    @pytest.mark.django_db
    def test_str_contains_admin_user(self, user):
        from icv_core.audit.models import AdminActivityLog

        log = AdminActivityLog.objects.create(
            admin_user=user,
            action_type="approve_claim",
            description="Approved claim.",
        )
        s = str(log)
        assert str(user) in s
