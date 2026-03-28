"""Tests for icv_core.audit.services."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from icv_core.audit.services import log_event, raise_alert, resolve_alert

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def audit_settings(settings):
    """Enable audit for the duration of a test."""
    settings.ICV_CORE_AUDIT_ENABLED = True
    settings.ICV_CORE_AUDIT_CAPTURE_IP = True
    settings.ICV_CORE_AUDIT_CAPTURE_USER_AGENT = True
    yield settings
    settings.ICV_CORE_AUDIT_ENABLED = False


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", email="testuser@example.com", password="testpass")


def _make_request(ip="1.2.3.4", ua="Mozilla/5.0", forwarded_for=None, user=None):
    """Build a minimal fake HttpRequest."""
    request = MagicMock()
    request.META = {
        "REMOTE_ADDR": ip,
        "HTTP_USER_AGENT": ua,
    }
    if forwarded_for:
        request.META["HTTP_X_FORWARDED_FOR"] = forwarded_for
    request.user = user
    return request


# ---------------------------------------------------------------------------
# log_event — audit disabled
# ---------------------------------------------------------------------------


class TestLogEventAuditDisabled:
    """log_event() is a no-op when ICV_CORE_AUDIT_ENABLED=False."""

    def test_returns_none_when_disabled(self, settings):
        settings.ICV_CORE_AUDIT_ENABLED = False
        result = log_event(event_type="DATA", action="CREATE")
        assert result is None

    def test_does_not_write_to_db_when_disabled(self, db, settings):
        from icv_core.audit.models import AuditEntry

        settings.ICV_CORE_AUDIT_ENABLED = False
        log_event(event_type="DATA", action="CREATE")
        assert AuditEntry.objects.count() == 0


# ---------------------------------------------------------------------------
# log_event — synchronous path
# ---------------------------------------------------------------------------


class TestLogEventSync:
    """log_event() writes an AuditEntry synchronously when audit is enabled."""

    @pytest.mark.django_db
    def test_creates_audit_entry(self, audit_settings):
        from icv_core.audit.models import AuditEntry

        entry = log_event(event_type="DATA", action="CREATE")

        assert entry is not None
        assert AuditEntry.objects.count() == 1
        assert entry.event_type == "DATA"
        assert entry.action == "CREATE"

    @pytest.mark.django_db
    def test_records_user(self, audit_settings, user):
        entry = log_event(event_type="SECURITY", action="LOGIN", user=user)
        assert entry.user == user

    @pytest.mark.django_db
    def test_records_description(self, audit_settings):
        entry = log_event(
            event_type="SYSTEM",
            action="CUSTOM",
            description="Something happened",
        )
        assert entry.description == "Something happened"

    @pytest.mark.django_db
    def test_records_metadata(self, audit_settings):
        entry = log_event(
            event_type="DATA",
            action="UPDATE",
            metadata={"field": "email", "old": "a@b.com"},
        )
        assert entry.metadata["field"] == "email"

    @pytest.mark.django_db
    def test_metadata_defaults_to_empty_dict(self, audit_settings):
        entry = log_event(event_type="DATA", action="DELETE")
        assert entry.metadata == {}

    @pytest.mark.django_db
    def test_records_ip_from_request(self, audit_settings):
        request = _make_request(ip="10.0.0.1")
        entry = log_event(event_type="SECURITY", action="PERMISSION_DENIED", request=request)
        assert entry.ip_address == "10.0.0.1"

    @pytest.mark.django_db
    def test_picks_first_ip_from_forwarded_for(self, audit_settings):
        request = _make_request(forwarded_for="203.0.113.1, 10.0.0.1")
        entry = log_event(event_type="DATA", action="CREATE", request=request)
        assert entry.ip_address == "203.0.113.1"

    @pytest.mark.django_db
    def test_records_user_agent_from_request(self, audit_settings):
        request = _make_request(ua="TestClient/1.0")
        entry = log_event(event_type="DATA", action="CREATE", request=request)
        assert entry.user_agent == "TestClient/1.0"

    @pytest.mark.django_db
    def test_ip_not_captured_when_setting_disabled(self, audit_settings):
        audit_settings.ICV_CORE_AUDIT_CAPTURE_IP = False
        request = _make_request(ip="10.0.0.2")
        entry = log_event(event_type="DATA", action="CREATE", request=request)
        assert entry.ip_address is None

    @pytest.mark.django_db
    def test_ua_not_captured_when_setting_disabled(self, audit_settings):
        audit_settings.ICV_CORE_AUDIT_CAPTURE_USER_AGENT = False
        request = _make_request(ua="TestClient/1.0")
        entry = log_event(event_type="DATA", action="CREATE", request=request)
        assert entry.user_agent == ""

    @pytest.mark.django_db
    def test_records_target_generic_fk(self, audit_settings, user):
        """target kwarg is stored as a GenericForeignKey on the AuditEntry."""
        entry = log_event(
            event_type="DATA",
            action="UPDATE",
            target=user,
        )
        assert entry.target == user
        assert entry.target_content_type is not None

    @pytest.mark.django_db
    def test_no_target_leaves_fk_null(self, audit_settings):
        entry = log_event(event_type="DATA", action="CREATE")
        assert entry.target_content_type is None
        assert entry.target_object_id is None

    @pytest.mark.django_db
    def test_falls_back_to_middleware_context(self, audit_settings, user):
        """When no request is passed, thread-local context from AuditRequestMiddleware is used."""
        ctx = {"ip_address": "9.9.9.9", "user_agent": "MiddlewareBot/1.0", "user": user}

        with patch("icv_core.audit.middleware.get_audit_context", return_value=ctx):
            entry = log_event(event_type="AUTHENTICATION", action="LOGIN")

        assert entry.ip_address == "9.9.9.9"
        assert entry.user_agent == "MiddlewareBot/1.0"
        assert entry.user == user

    @pytest.mark.django_db
    def test_explicit_user_takes_precedence_over_context(self, audit_settings, user):
        """An explicit user kwarg is not overridden by thread-local context."""
        other_user = User.objects.create_user(username="other", email="other@example.com", password="x")
        ctx = {"user": other_user}

        with patch("icv_core.audit.middleware.get_audit_context", return_value=ctx):
            entry = log_event(
                event_type="AUTHENTICATION",
                action="LOGOUT",
                user=user,
            )

        assert entry.user == user


# ---------------------------------------------------------------------------
# log_event — async path
# ---------------------------------------------------------------------------


class TestLogEventAsync:
    def test_enqueues_celery_task_and_returns_none(self, audit_settings):
        mock_task = MagicMock()

        with patch("icv_core.audit.tasks.log_event_async", mock_task):
            result = log_event(
                event_type="DATA",
                action="CREATE",
                async_mode=True,
            )

        assert result is None
        mock_task.delay.assert_called_once()

    def test_async_passes_user_id(self, audit_settings, user):
        mock_task = MagicMock()

        with patch("icv_core.audit.tasks.log_event_async", mock_task):
            log_event(event_type="DATA", action="CREATE", user=user, async_mode=True)

        call_kwargs = mock_task.delay.call_args.kwargs
        assert call_kwargs["user_id"] == str(user.pk)

    def test_async_with_no_user_passes_none(self, audit_settings):
        mock_task = MagicMock()

        with patch("icv_core.audit.tasks.log_event_async", mock_task):
            log_event(event_type="DATA", action="DELETE", async_mode=True)

        call_kwargs = mock_task.delay.call_args.kwargs
        assert call_kwargs["user_id"] is None

    def test_async_returns_none_when_audit_disabled(self, settings):
        settings.ICV_CORE_AUDIT_ENABLED = False
        mock_task = MagicMock()

        with patch("icv_core.audit.tasks.log_event_async", mock_task):
            result = log_event(event_type="DATA", action="CREATE", async_mode=True)

        assert result is None
        mock_task.delay.assert_not_called()


# ---------------------------------------------------------------------------
# raise_alert
# ---------------------------------------------------------------------------


class TestRaiseAlert:
    @pytest.mark.django_db
    def test_creates_system_alert(self):
        from icv_core.audit.models import SystemAlert

        alert = raise_alert(
            alert_type="security",
            severity="warning",
            title="Test alert",
            message="Something looks suspicious.",
        )

        assert SystemAlert.objects.count() == 1
        assert alert.alert_type == "security"
        assert alert.severity == "warning"
        assert alert.title == "Test alert"

    @pytest.mark.django_db
    def test_alert_is_unresolved_by_default(self):
        alert = raise_alert(
            alert_type="system",
            severity="info",
            title="Info alert",
            message="FYI.",
        )
        assert alert.is_resolved is False

    @pytest.mark.django_db
    def test_metadata_stored(self):
        alert = raise_alert(
            alert_type="payment",
            severity="error",
            title="Payment failure",
            message="Stripe returned an error.",
            metadata={"stripe_error": "card_declined"},
        )
        assert alert.metadata["stripe_error"] == "card_declined"

    @pytest.mark.django_db
    def test_metadata_defaults_to_empty_dict(self):
        alert = raise_alert(
            alert_type="system",
            severity="info",
            title="No meta",
            message="No extra context.",
        )
        assert alert.metadata == {}

    @pytest.mark.django_db
    def test_fires_system_alert_raised_signal(self):
        from icv_core.audit.signals import system_alert_raised

        received = []

        def handler(sender, instance, **kw):
            received.append(instance)

        system_alert_raised.connect(handler, dispatch_uid="test_signal_handler")
        try:
            alert = raise_alert(
                alert_type="support",
                severity="critical",
                title="Critical issue",
                message="Need attention now.",
            )
        finally:
            system_alert_raised.disconnect(handler, dispatch_uid="test_signal_handler")

        assert len(received) == 1
        assert received[0] == alert

    def test_raises_for_invalid_severity(self, settings):
        settings.ICV_CORE_AUDIT_ALERT_SEVERITY_LEVELS = ["info", "warning", "error", "critical"]

        with pytest.raises(ValueError, match="Invalid severity"):
            raise_alert(
                alert_type="system",
                severity="catastrophic",
                title="Bad severity",
                message="Should not be created.",
            )

    @pytest.mark.django_db
    def test_respects_custom_severity_levels(self, settings):
        settings.ICV_CORE_AUDIT_ALERT_SEVERITY_LEVELS = ["low", "medium", "high"]

        alert = raise_alert(
            alert_type="system",
            severity="high",
            title="High alert",
            message="Using custom levels.",
        )
        assert alert.severity == "high"


# ---------------------------------------------------------------------------
# resolve_alert
# ---------------------------------------------------------------------------


class TestResolveAlert:
    @pytest.mark.django_db
    def test_resolves_alert(self, user):
        alert = raise_alert(
            alert_type="system",
            severity="info",
            title="Resolvable",
            message="Should be resolved.",
        )
        resolved = resolve_alert(alert, resolved_by=user, notes="All clear.")

        resolved.refresh_from_db()
        assert resolved.is_resolved is True
        assert resolved.resolved_by == user
        assert resolved.resolution_notes == "All clear."
        assert resolved.resolved_at is not None

    @pytest.mark.django_db
    def test_returns_same_alert_instance(self, user):
        alert = raise_alert(
            alert_type="system",
            severity="info",
            title="Return check",
            message=".",
        )
        result = resolve_alert(alert, resolved_by=user)
        assert result is alert

    @pytest.mark.django_db
    def test_raises_when_already_resolved(self, user):
        alert = raise_alert(
            alert_type="system",
            severity="info",
            title="Already done",
            message=".",
        )
        resolve_alert(alert, resolved_by=user)

        with pytest.raises(ValueError, match="already resolved"):
            resolve_alert(alert, resolved_by=user)


# ---------------------------------------------------------------------------
# services __init__ re-exports
# ---------------------------------------------------------------------------


class TestServicesInit:
    def test_log_event_importable_from_services(self):
        from icv_core.services import log_event as imported

        assert imported is log_event

    def test_raise_alert_importable_from_services(self):
        from icv_core.services import raise_alert as imported

        assert imported is raise_alert

    def test_resolve_alert_importable_from_services(self):
        from icv_core.services import resolve_alert as imported

        assert imported is resolve_alert
