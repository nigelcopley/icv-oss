"""Tests for icv-core settings/conf module."""


class TestGetSetting:
    """get_setting() returns values from Django settings with fallback defaults."""

    def test_returns_default_when_setting_absent(self):
        from icv_core.conf import get_setting

        result = get_setting("NONEXISTENT_KEY_XYZ", "my_default")
        assert result == "my_default"

    def test_returns_override_from_django_settings(self, settings):
        settings.ICV_CORE_TEST_KEY = "overridden"
        from icv_core.conf import get_setting

        result = get_setting("TEST_KEY", "fallback")
        assert result == "overridden"

    def test_returns_none_when_no_default_given(self):
        from icv_core.conf import get_setting

        result = get_setting("ANOTHER_NONEXISTENT_KEY_ABC")
        assert result is None


class TestDefaultSettings:
    """Module-level settings have correct defaults."""

    def test_uuid_version_default(self):
        from icv_core import conf

        assert conf.ICV_CORE_UUID_VERSION == 4

    def test_allow_hard_delete_default(self):
        from icv_core import conf

        assert conf.ICV_CORE_ALLOW_HARD_DELETE is False

    def test_audit_enabled_default(self):
        from icv_core import conf

        assert conf.ICV_CORE_AUDIT_ENABLED is False

    def test_audit_retention_days_default(self):
        from icv_core import conf

        assert conf.ICV_CORE_AUDIT_RETENTION_DAYS == 365

    def test_track_created_by_default(self):
        from icv_core import conf

        assert conf.ICV_CORE_TRACK_CREATED_BY is False
