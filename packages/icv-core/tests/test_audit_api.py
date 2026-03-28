"""
Tests for the audit API viewsets, serializers, and AuditRequestMiddleware.

Coverage targets:
  - icv_core/audit/middleware.py      (AuditRequestMiddleware)
  - icv_core/audit/api/serializers.py (AuditEntry/AdminActivityLog/SystemAlert)
  - icv_core/audit/api/views.py       (all three viewsets + resolve action)

Notes:
  - DRF is an optional dependency; the entire module is skipped when absent.
  - icv_core.conf constants are module-level (evaluated at import time), so
    tests that control IP/UA capture must patch icv_core.conf directly.
  - Viewset tests inject a minimal ROOT_URLCONF that mounts the audit router
    without touching INSTALLED_APPS (rest_framework is already present in the
    sandbox settings that pytest uses).
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

rest_framework = pytest.importorskip("rest_framework")

from django.contrib.auth import get_user_model  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.test import RequestFactory  # noqa: E402


def _get_results(response_data):
    """Extract results from paginated or unpaginated DRF response."""
    if isinstance(response_data, list):
        return response_data
    return response_data.get("results", response_data)


from rest_framework import status  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from icv_core.audit.middleware import (  # noqa: E402
    AuditRequestMiddleware,
    _audit_context,
    get_audit_context,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="testpass",
        is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        username="regular",
        email="regular@example.com",
        password="testpass",
        is_staff=False,
    )


@pytest.fixture
def audit_entry(db, staff_user):
    """Create an AuditEntry directly (bypasses service layer)."""
    from icv_core.audit.models import AuditEntry

    return AuditEntry.objects.create(
        event_type=AuditEntry.EventType.DATA,
        action=AuditEntry.Action.CREATE,
        user=staff_user,
        ip_address="1.2.3.4",
        user_agent="TestClient/1.0",
        description="Test entry",
        metadata={"key": "value"},
    )


@pytest.fixture
def admin_log(db, staff_user):
    """Create an AdminActivityLog directly."""
    from icv_core.audit.models import AdminActivityLog

    return AdminActivityLog.objects.create(
        admin_user=staff_user,
        action_type="approve_claim",
        description="Approved a claim",
        ip_address="2.3.4.5",
    )


@pytest.fixture
def system_alert(db):
    """Create an unresolved SystemAlert directly."""
    from icv_core.audit.models import SystemAlert

    return SystemAlert.objects.create(
        alert_type=SystemAlert.AlertType.SECURITY,
        severity="warning",
        title="Suspicious login",
        message="Multiple failed attempts.",
    )


# ---------------------------------------------------------------------------
# URL config fixture shared by all viewset test classes
# ---------------------------------------------------------------------------


@pytest.fixture
def audit_urls(settings):
    """
    Register a minimal ROOT_URLCONF that mounts the audit API router at
    /api/audit/. Also enables django-filter so that filterset_fields on the
    viewsets actually filter (requires DEFAULT_FILTER_BACKENDS).

    Cleans up the temporary urlconf module from sys.modules on teardown.
    """
    from django.urls import include, path

    # Enable django-filter backend so filterset_fields works in tests
    existing_rf = getattr(settings, "REST_FRAMEWORK", {}).copy()
    existing_rf.setdefault(
        "DEFAULT_FILTER_BACKENDS",
        [
            "django_filters.rest_framework.DjangoFilterBackend",
        ],
    )
    settings.REST_FRAMEWORK = existing_rf

    # Ensure django_filters is in INSTALLED_APPS (idempotent)
    if "django_filters" not in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS = list(settings.INSTALLED_APPS) + ["django_filters"]

    mod_name = "_test_audit_api_urlconf"
    mod = types.ModuleType(mod_name)
    mod.urlpatterns = [
        path("api/audit/", include("icv_core.audit.api.urls")),
    ]
    sys.modules[mod_name] = mod
    settings.ROOT_URLCONF = mod_name
    yield
    sys.modules.pop(mod_name, None)


# ---------------------------------------------------------------------------
# AuditRequestMiddleware
# ---------------------------------------------------------------------------


class TestAuditRequestMiddleware:
    """AuditRequestMiddleware populates and clears the thread-local audit context."""

    def _make_middleware(self):
        return AuditRequestMiddleware(get_response=lambda r: HttpResponse())

    # --- IP capture ---

    def test_ip_captured_from_remote_addr(self, rf):
        with (
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_IP", True),
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_USER_AGENT", False),
        ):
            request = rf.get("/", REMOTE_ADDR="10.0.0.1")
            self._make_middleware().process_request(request)
            assert _audit_context.context.get("ip_address") == "10.0.0.1"
        _audit_context.context = {}

    def test_ip_captured_from_x_forwarded_for_first_entry(self, rf):
        with (
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_IP", True),
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_USER_AGENT", False),
        ):
            request = rf.get(
                "/",
                REMOTE_ADDR="10.0.0.1",
                HTTP_X_FORWARDED_FOR="203.0.113.5, 10.0.0.1",
            )
            self._make_middleware().process_request(request)
            assert _audit_context.context.get("ip_address") == "203.0.113.5"
        _audit_context.context = {}

    def test_ip_captured_from_x_forwarded_for_single_ip(self, rf):
        with (
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_IP", True),
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_USER_AGENT", False),
        ):
            request = rf.get("/", HTTP_X_FORWARDED_FOR="192.168.1.1")
            self._make_middleware().process_request(request)
            assert _audit_context.context.get("ip_address") == "192.168.1.1"
        _audit_context.context = {}

    def test_ip_not_captured_when_setting_disabled(self, rf):
        with (
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_IP", False),
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_USER_AGENT", False),
        ):
            request = rf.get("/", REMOTE_ADDR="9.9.9.9")
            self._make_middleware().process_request(request)
            assert "ip_address" not in _audit_context.context
        _audit_context.context = {}

    # --- User-agent capture ---

    def test_user_agent_captured_from_meta(self, rf):
        with (
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_IP", False),
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_USER_AGENT", True),
        ):
            request = rf.get("/", HTTP_USER_AGENT="MyBrowser/2.0")
            self._make_middleware().process_request(request)
            assert _audit_context.context.get("user_agent") == "MyBrowser/2.0"
        _audit_context.context = {}

    def test_user_agent_not_captured_when_setting_disabled(self, rf):
        with (
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_IP", False),
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_USER_AGENT", False),
        ):
            request = rf.get("/", HTTP_USER_AGENT="SomeBot/1.0")
            self._make_middleware().process_request(request)
            assert "user_agent" not in _audit_context.context
        _audit_context.context = {}

    # --- User capture ---

    def test_user_set_from_request(self, rf, db):
        with (
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_IP", False),
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_USER_AGENT", False),
        ):
            user = User.objects.create_user(username="u", email="u@example.com", password="pw")
            request = rf.get("/")
            request.user = user
            self._make_middleware().process_request(request)
            assert _audit_context.context.get("user") is user
        _audit_context.context = {}

    def test_user_is_none_when_request_has_no_user_attr(self, rf):
        with (
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_IP", False),
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_USER_AGENT", False),
        ):
            request = rf.get("/")
            # Explicitly strip the user attribute if RequestFactory set it
            if hasattr(request, "user"):
                del request.user
            self._make_middleware().process_request(request)
            assert _audit_context.context.get("user") is None
        _audit_context.context = {}

    # --- Teardown (context clearing) ---

    def test_process_response_clears_context(self, rf):
        with (
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_IP", True),
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_USER_AGENT", True),
        ):
            request = rf.get("/", REMOTE_ADDR="1.1.1.1")
            mw = self._make_middleware()
            mw.process_request(request)
            assert _audit_context.context  # non-empty after request
            mw.process_response(request, HttpResponse())
            assert _audit_context.context == {}

    def test_process_exception_clears_context(self, rf):
        with (
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_IP", True),
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_USER_AGENT", True),
        ):
            request = rf.get("/", REMOTE_ADDR="2.2.2.2")
            mw = self._make_middleware()
            mw.process_request(request)
            assert _audit_context.context
            mw.process_exception(request, RuntimeError("boom"))
            assert _audit_context.context == {}

    # --- get_audit_context helper ---

    def test_get_audit_context_returns_empty_outside_request(self):
        _audit_context.context = {}
        assert get_audit_context() == {}

    def test_get_audit_context_returns_empty_when_attribute_absent(self):
        # Simulate a fresh thread where .context was never set
        if hasattr(_audit_context, "context"):
            del _audit_context.context
        assert get_audit_context() == {}
        # Restore clean state
        _audit_context.context = {}

    def test_get_audit_context_returns_populated_context(self, rf):
        with (
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_IP", True),
            patch("icv_core.conf.ICV_CORE_AUDIT_CAPTURE_USER_AGENT", False),
        ):
            request = rf.get("/", REMOTE_ADDR="5.5.5.5")
            mw = self._make_middleware()
            mw.process_request(request)
            ctx = get_audit_context()
            assert ctx.get("ip_address") == "5.5.5.5"
        _audit_context.context = {}


# ---------------------------------------------------------------------------
# Serializer tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditEntrySerializer:
    """AuditEntrySerializer covers all declared fields and is fully read-only."""

    def test_serialises_all_expected_fields(self, audit_entry):
        from icv_core.audit.api.serializers import AuditEntrySerializer

        data = AuditEntrySerializer(audit_entry).data
        expected_fields = {
            "id",
            "event_type",
            "action",
            "user",
            "ip_address",
            "user_agent",
            "target_content_type",
            "target_object_id",
            "description",
            "metadata",
            "created_at",
        }
        assert set(data.keys()) == expected_fields

    def test_serialised_values_are_correct(self, audit_entry, staff_user):
        from icv_core.audit.api.serializers import AuditEntrySerializer

        data = AuditEntrySerializer(audit_entry).data
        assert data["event_type"] == "DATA"
        assert data["action"] == "CREATE"
        assert data["ip_address"] == "1.2.3.4"
        assert data["user_agent"] == "TestClient/1.0"
        assert data["description"] == "Test entry"
        assert data["metadata"] == {"key": "value"}
        # DRF serialises FK as the raw PK value (UUID object or string both compare equal)
        assert data["user"] == staff_user.pk

    def test_all_fields_are_read_only(self):
        from icv_core.audit.api.serializers import AuditEntrySerializer

        serializer = AuditEntrySerializer()
        for field_name, field in serializer.fields.items():
            assert field.read_only, f"Field '{field_name}' should be read-only"

    def test_write_attempt_produces_no_validated_data(self, audit_entry):
        """Submitting data to a fully read-only serializer yields no validated_data."""
        from icv_core.audit.api.serializers import AuditEntrySerializer

        serializer = AuditEntrySerializer(
            audit_entry,
            data={"event_type": "SECURITY", "action": "DELETE"},
        )
        # All fields read-only → DRF considers the payload valid but ignores
        # every field, resulting in empty validated_data.
        assert serializer.is_valid()
        assert serializer.validated_data == {}


@pytest.mark.django_db
class TestAdminActivityLogSerializer:
    """AdminActivityLogSerializer covers all declared fields and is fully read-only."""

    def test_serialises_all_expected_fields(self, admin_log):
        from icv_core.audit.api.serializers import AdminActivityLogSerializer

        data = AdminActivityLogSerializer(admin_log).data
        expected_fields = {
            "id",
            "admin_user",
            "action_type",
            "description",
            "target_content_type",
            "target_object_id",
            "ip_address",
            "user_agent",
            "metadata",
            "created_at",
        }
        assert set(data.keys()) == expected_fields

    def test_serialised_values_are_correct(self, admin_log, staff_user):
        from icv_core.audit.api.serializers import AdminActivityLogSerializer

        data = AdminActivityLogSerializer(admin_log).data
        assert data["action_type"] == "approve_claim"
        assert data["description"] == "Approved a claim"
        assert data["ip_address"] == "2.3.4.5"
        assert data["admin_user"] == staff_user.pk

    def test_all_fields_are_read_only(self):
        from icv_core.audit.api.serializers import AdminActivityLogSerializer

        serializer = AdminActivityLogSerializer()
        for field_name, field in serializer.fields.items():
            assert field.read_only, f"Field '{field_name}' should be read-only"


@pytest.mark.django_db
class TestSystemAlertSerializer:
    """SystemAlertSerializer has a mix of read-only and writable fields."""

    def test_serialises_all_expected_fields(self, system_alert):
        from icv_core.audit.api.serializers import SystemAlertSerializer

        data = SystemAlertSerializer(system_alert).data
        expected_fields = {
            "id",
            "alert_type",
            "severity",
            "title",
            "message",
            "metadata",
            "is_resolved",
            "resolved_by",
            "resolved_at",
            "resolution_notes",
            "created_at",
            "updated_at",
        }
        assert set(data.keys()) == expected_fields

    def test_serialised_values_are_correct(self, system_alert):
        from icv_core.audit.api.serializers import SystemAlertSerializer

        data = SystemAlertSerializer(system_alert).data
        assert data["alert_type"] == "security"
        assert data["severity"] == "warning"
        assert data["title"] == "Suspicious login"
        assert data["message"] == "Multiple failed attempts."
        assert data["is_resolved"] is False
        assert data["resolved_by"] is None
        assert data["resolved_at"] is None

    def test_read_only_fields_are_enforced(self):
        """Declared read_only_fields on SystemAlertSerializer are honoured."""
        from icv_core.audit.api.serializers import SystemAlertSerializer

        read_only = {
            "id",
            "is_resolved",
            "resolved_by",
            "resolved_at",
            "created_at",
            "updated_at",
        }
        serializer = SystemAlertSerializer()
        for field_name in read_only:
            assert serializer.fields[field_name].read_only, f"Field '{field_name}' should be read-only"

    def test_writable_fields_accept_valid_data(self):
        from icv_core.audit.api.serializers import SystemAlertSerializer

        payload = {
            "alert_type": "payment",
            "severity": "error",
            "title": "Payment declined",
            "message": "Card rejected.",
        }
        serializer = SystemAlertSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors

    def test_title_is_required_for_creation(self):
        from icv_core.audit.api.serializers import SystemAlertSerializer

        serializer = SystemAlertSerializer(
            data={
                "alert_type": "system",
                "severity": "info",
                "message": "No title provided.",
            }
        )
        assert not serializer.is_valid()
        assert "title" in serializer.errors

    def test_resolution_notes_field_is_writable(self):
        from icv_core.audit.api.serializers import SystemAlertSerializer

        serializer = SystemAlertSerializer()
        assert not serializer.fields["resolution_notes"].read_only


# ---------------------------------------------------------------------------
# IsStaff permission class
# ---------------------------------------------------------------------------


class TestIsStaffPermission:
    """IsStaff.has_permission grants access only to authenticated staff users."""

    def _check(self, is_authenticated: bool, is_staff: bool) -> bool:
        from icv_core.audit.api.views import IsStaff

        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = is_authenticated
        request.user.is_staff = is_staff
        return IsStaff().has_permission(request, view=None)

    def test_staff_authenticated_user_is_allowed(self):
        assert self._check(is_authenticated=True, is_staff=True) is True

    def test_non_staff_authenticated_user_is_denied(self):
        assert self._check(is_authenticated=True, is_staff=False) is False

    def test_unauthenticated_user_is_denied(self):
        assert self._check(is_authenticated=False, is_staff=False) is False

    def test_unauthenticated_with_staff_flag_is_denied(self):
        """is_staff=True means nothing without authentication."""
        assert self._check(is_authenticated=False, is_staff=True) is False

    def test_none_user_is_denied(self):
        from icv_core.audit.api.views import IsStaff

        request = MagicMock()
        request.user = None
        assert IsStaff().has_permission(request, view=None) is False


# ---------------------------------------------------------------------------
# AuditEntryViewSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditEntryViewSet:
    """AuditEntry endpoints are read-only and staff-only."""

    LIST_URL = "/api/audit/entries/"

    @pytest.fixture(autouse=True)
    def _urls(self, audit_urls):
        pass

    def test_list_returns_200_for_staff(self, api_client, staff_user, audit_entry):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_audit_entries(self, api_client, staff_user, audit_entry):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL)
        results = _get_results(response.data)
        assert len(results) >= 1

    def test_list_denies_anonymous(self, api_client):
        response = api_client.get(self.LIST_URL)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_list_denies_non_staff(self, api_client, regular_user):
        api_client.force_authenticate(user=regular_user)
        response = api_client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_detail_returns_200_for_staff(self, api_client, staff_user, audit_entry):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(f"{self.LIST_URL}{audit_entry.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_detail_contains_expected_fields(self, api_client, staff_user, audit_entry):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(f"{self.LIST_URL}{audit_entry.pk}/")
        data = response.data
        for field in ("event_type", "action", "ip_address", "user_agent", "created_at"):
            assert field in data, f"Expected '{field}' in response"

    def test_post_returns_405(self, api_client, staff_user):
        api_client.force_authenticate(user=staff_user)
        response = api_client.post(
            self.LIST_URL,
            {"event_type": "DATA", "action": "CREATE"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_put_returns_405(self, api_client, staff_user, audit_entry):
        api_client.force_authenticate(user=staff_user)
        response = api_client.put(
            f"{self.LIST_URL}{audit_entry.pk}/",
            {"event_type": "SECURITY", "action": "DELETE"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_returns_405(self, api_client, staff_user, audit_entry):
        api_client.force_authenticate(user=staff_user)
        response = api_client.delete(f"{self.LIST_URL}{audit_entry.pk}/")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_filter_by_event_type(self, api_client, staff_user):
        from icv_core.audit.models import AuditEntry

        AuditEntry.objects.create(
            event_type=AuditEntry.EventType.SECURITY,
            action=AuditEntry.Action.LOGIN,
        )
        AuditEntry.objects.create(
            event_type=AuditEntry.EventType.DATA,
            action=AuditEntry.Action.CREATE,
        )
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL, {"event_type": "SECURITY"})
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response.data)
        assert all(r["event_type"] == "SECURITY" for r in results)

    def test_filter_by_action(self, api_client, staff_user):
        from icv_core.audit.models import AuditEntry

        AuditEntry.objects.create(
            event_type=AuditEntry.EventType.DATA,
            action=AuditEntry.Action.DELETE,
        )
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL, {"action": "DELETE"})
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response.data)
        assert all(r["action"] == "DELETE" for r in results)


# ---------------------------------------------------------------------------
# AdminActivityLogViewSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdminActivityLogViewSet:
    """AdminActivityLog endpoints are read-only and staff-only."""

    LIST_URL = "/api/audit/admin-activity/"

    @pytest.fixture(autouse=True)
    def _urls(self, audit_urls):
        pass

    def test_list_returns_200_for_staff(self, api_client, staff_user, admin_log):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_admin_logs(self, api_client, staff_user, admin_log):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL)
        results = _get_results(response.data)
        assert len(results) >= 1

    def test_list_denies_anonymous(self, api_client):
        response = api_client.get(self.LIST_URL)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_list_denies_non_staff(self, api_client, regular_user):
        api_client.force_authenticate(user=regular_user)
        response = api_client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_detail_returns_200_for_staff(self, api_client, staff_user, admin_log):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(f"{self.LIST_URL}{admin_log.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_detail_contains_expected_fields(self, api_client, staff_user, admin_log):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(f"{self.LIST_URL}{admin_log.pk}/")
        data = response.data
        for field in ("action_type", "description", "admin_user", "ip_address"):
            assert field in data, f"Expected '{field}' in response"

    def test_post_returns_405(self, api_client, staff_user):
        api_client.force_authenticate(user=staff_user)
        response = api_client.post(
            self.LIST_URL,
            {"action_type": "foo", "description": "bar"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_put_returns_405(self, api_client, staff_user, admin_log):
        api_client.force_authenticate(user=staff_user)
        response = api_client.put(
            f"{self.LIST_URL}{admin_log.pk}/",
            {"action_type": "new_action"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_returns_405(self, api_client, staff_user, admin_log):
        api_client.force_authenticate(user=staff_user)
        response = api_client.delete(f"{self.LIST_URL}{admin_log.pk}/")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_filter_by_action_type(self, api_client, staff_user):
        from icv_core.audit.models import AdminActivityLog

        AdminActivityLog.objects.create(
            admin_user=staff_user,
            action_type="ban_user",
            description="Banned a user",
        )
        AdminActivityLog.objects.create(
            admin_user=staff_user,
            action_type="verify_coach",
            description="Verified a coach",
        )
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL, {"action_type": "ban_user"})
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response.data)
        assert all(r["action_type"] == "ban_user" for r in results)


# ---------------------------------------------------------------------------
# SystemAlertViewSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSystemAlertViewSet:
    """SystemAlert endpoints support CRUD for staff; resolve is a custom action."""

    LIST_URL = "/api/audit/alerts/"

    @pytest.fixture(autouse=True)
    def _urls(self, audit_urls):
        pass

    def test_list_returns_200_for_staff(self, api_client, staff_user, system_alert):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_alerts(self, api_client, staff_user, system_alert):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL)
        results = _get_results(response.data)
        assert len(results) >= 1

    def test_list_denies_anonymous(self, api_client):
        response = api_client.get(self.LIST_URL)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_list_denies_non_staff(self, api_client, regular_user):
        api_client.force_authenticate(user=regular_user)
        response = api_client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_detail_returns_200_for_staff(self, api_client, staff_user, system_alert):
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(f"{self.LIST_URL}{system_alert.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_create_alert_returns_201(self, api_client, staff_user):
        from icv_core.audit.models import SystemAlert

        api_client.force_authenticate(user=staff_user)
        payload = {
            "alert_type": "payment",
            "severity": "error",
            "title": "Card declined",
            "message": "Stripe returned card_declined.",
        }
        response = api_client.post(self.LIST_URL, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert SystemAlert.objects.filter(title="Card declined").exists()

    def test_create_alert_response_contains_correct_data(self, api_client, staff_user):
        api_client.force_authenticate(user=staff_user)
        payload = {
            "alert_type": "system",
            "severity": "info",
            "title": "Disk space low",
            "message": "Server disk at 90%.",
        }
        response = api_client.post(self.LIST_URL, payload, format="json")
        assert response.data["title"] == "Disk space low"
        assert response.data["is_resolved"] is False

    def test_create_alert_denied_for_non_staff(self, api_client, regular_user):
        api_client.force_authenticate(user=regular_user)
        payload = {
            "alert_type": "system",
            "severity": "info",
            "title": "Should fail",
            "message": ".",
        }
        response = api_client.post(self.LIST_URL, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_alert_with_put(self, api_client, staff_user, system_alert):
        api_client.force_authenticate(user=staff_user)
        payload = {
            "alert_type": system_alert.alert_type,
            "severity": system_alert.severity,
            "title": "Updated title",
            "message": system_alert.message,
        }
        response = api_client.put(f"{self.LIST_URL}{system_alert.pk}/", payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        system_alert.refresh_from_db()
        assert system_alert.title == "Updated title"

    def test_partial_update_alert_with_patch(self, api_client, staff_user, system_alert):
        api_client.force_authenticate(user=staff_user)
        response = api_client.patch(
            f"{self.LIST_URL}{system_alert.pk}/",
            {"title": "Patched title"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        system_alert.refresh_from_db()
        assert system_alert.title == "Patched title"

    def test_delete_alert(self, api_client, staff_user, system_alert):
        from icv_core.audit.models import SystemAlert

        api_client.force_authenticate(user=staff_user)
        pk = system_alert.pk
        response = api_client.delete(f"{self.LIST_URL}{pk}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not SystemAlert.objects.filter(pk=pk).exists()

    # --- resolve custom action ---

    def test_resolve_marks_alert_resolved(self, api_client, staff_user, system_alert):
        api_client.force_authenticate(user=staff_user)
        response = api_client.post(
            f"{self.LIST_URL}{system_alert.pk}/resolve/",
            {"resolution_notes": "All clear."},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        system_alert.refresh_from_db()
        assert system_alert.is_resolved is True
        assert system_alert.resolved_by == staff_user
        assert system_alert.resolution_notes == "All clear."

    def test_resolve_returns_serialised_alert(self, api_client, staff_user, system_alert):
        api_client.force_authenticate(user=staff_user)
        response = api_client.post(
            f"{self.LIST_URL}{system_alert.pk}/resolve/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_resolved"] is True
        assert response.data["resolved_at"] is not None

    def test_resolve_already_resolved_returns_400(self, api_client, staff_user, system_alert):
        """Resolving an alert that is already resolved returns 400."""
        system_alert.resolve(resolved_by=staff_user, notes="First resolution")
        api_client.force_authenticate(user=staff_user)
        response = api_client.post(
            f"{self.LIST_URL}{system_alert.pk}/resolve/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already resolved" in response.data["detail"].lower()

    def test_resolve_without_notes_uses_empty_string(self, api_client, staff_user, system_alert):
        api_client.force_authenticate(user=staff_user)
        api_client.post(
            f"{self.LIST_URL}{system_alert.pk}/resolve/",
            {},
            format="json",
        )
        system_alert.refresh_from_db()
        assert system_alert.resolution_notes == ""

    def test_resolve_denied_for_non_staff(self, api_client, regular_user, system_alert):
        api_client.force_authenticate(user=regular_user)
        response = api_client.post(
            f"{self.LIST_URL}{system_alert.pk}/resolve/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # --- filtering ---

    def test_filter_by_alert_type(self, api_client, staff_user):
        from icv_core.audit.models import SystemAlert

        SystemAlert.objects.create(alert_type="security", severity="warning", title="Sec", message=".")
        SystemAlert.objects.create(alert_type="payment", severity="error", title="Pay", message=".")
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL, {"alert_type": "security"})
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response.data)
        assert all(r["alert_type"] == "security" for r in results)

    def test_filter_by_is_resolved_false(self, api_client, staff_user):
        from icv_core.audit.models import SystemAlert

        resolved = SystemAlert.objects.create(alert_type="system", severity="info", title="Resolved", message=".")
        resolved.resolve(resolved_by=staff_user)
        SystemAlert.objects.create(alert_type="system", severity="info", title="Active", message=".")
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL, {"is_resolved": "false"})
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response.data)
        assert all(r["is_resolved"] is False for r in results)

    def test_filter_by_severity(self, api_client, staff_user):
        from icv_core.audit.models import SystemAlert

        SystemAlert.objects.create(alert_type="system", severity="critical", title="Crit", message=".")
        SystemAlert.objects.create(alert_type="system", severity="info", title="Info", message=".")
        api_client.force_authenticate(user=staff_user)
        response = api_client.get(self.LIST_URL, {"severity": "critical"})
        assert response.status_code == status.HTTP_200_OK
        results = _get_results(response.data)
        assert all(r["severity"] == "critical" for r in results)
