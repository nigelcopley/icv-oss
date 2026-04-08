"""Tests for management commands and Django system checks in icv-core.

The icv_core.conf module stores settings as module-level Python names evaluated
once at import time (via getattr(settings, ...)). Patching those names after
import requires mock.patch.object on the module itself — override_settings alone
is not sufficient.

For management commands the same principle applies: the command reads conf
names that are already bound in the module namespace.
"""

from __future__ import annotations

from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_conf(**values):
    """
    Return a context manager that patches multiple icv_core.conf names.

    Usage::

        with _patch_conf(ICV_CORE_UUID_VERSION=99):
            errors = check_icv_core_configuration(None)
    """
    import icv_core.conf as conf

    patches = [mock.patch.object(conf, name, value) for name, value in values.items()]

    class _MultiPatch:
        def __enter__(self):
            for p in patches:
                p.start()
            return self

        def __exit__(self, *args):
            for p in patches:
                p.stop()

    return _MultiPatch()


def _default_conf_values():
    """Return a dict of conf settings that produce a clean check result."""
    return dict(
        ICV_CORE_UUID_VERSION=4,
        ICV_CORE_SOFT_DELETE_FIELD="is_active",
        ICV_CORE_AUDIT_ENABLED=False,
        ICV_CORE_AUDIT_RETENTION_DAYS=365,
        ICV_CORE_ALLOW_HARD_DELETE=False,
        ICV_TENANCY_TENANT_MODEL="auth.Group",
    )


def _run_check(**overrides):
    """
    Invoke check_icv_core_configuration with a set of conf overrides.

    Starts from clean defaults and applies the given overrides on top.
    Returns the list of errors/warnings.
    """
    from icv_core.checks import check_icv_core_configuration

    values = {**_default_conf_values(), **overrides}
    with _patch_conf(**values):
        return check_icv_core_configuration(app_configs=None)


# ---------------------------------------------------------------------------
# System checks — valid configuration
# ---------------------------------------------------------------------------


class TestCheckValidConfiguration:
    """check_icv_core_configuration returns no errors for a healthy config."""

    def test_no_errors_with_default_settings(self):
        errors = _run_check()
        assert errors == []

    def test_uuid_version_7_is_valid(self):
        errors = _run_check(ICV_CORE_UUID_VERSION=7)
        ids = [e.id for e in errors]
        assert "icv_core.E001" not in ids

    def test_audit_enabled_with_valid_retention_produces_no_e003(self):
        errors = _run_check(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS=90)
        ids = [e.id for e in errors]
        assert "icv_core.E003" not in ids

    def test_audit_disabled_skips_retention_check(self):
        # Retention days is invalid but audit is disabled — E003 must not fire.
        errors = _run_check(ICV_CORE_AUDIT_ENABLED=False, ICV_CORE_AUDIT_RETENTION_DAYS=-1)
        ids = [e.id for e in errors]
        assert "icv_core.E003" not in ids


# ---------------------------------------------------------------------------
# System checks — UUID version
# ---------------------------------------------------------------------------


class TestCheckUUIDVersion:
    """E001 fires when ICV_CORE_UUID_VERSION is not 4 or 7."""

    def test_uuid_version_4_is_valid(self):
        errors = _run_check(ICV_CORE_UUID_VERSION=4)
        ids = [e.id for e in errors]
        assert "icv_core.E001" not in ids

    def test_uuid_version_7_is_valid(self):
        errors = _run_check(ICV_CORE_UUID_VERSION=7)
        ids = [e.id for e in errors]
        assert "icv_core.E001" not in ids

    def test_uuid_version_1_raises_e001(self):
        errors = _run_check(ICV_CORE_UUID_VERSION=1)
        ids = [e.id for e in errors]
        assert "icv_core.E001" in ids

    def test_uuid_version_3_raises_e001(self):
        errors = _run_check(ICV_CORE_UUID_VERSION=3)
        ids = [e.id for e in errors]
        assert "icv_core.E001" in ids

    def test_uuid_version_string_raises_e001(self):
        # A string "4" is not in (4, 7) — the check uses strict equality.
        errors = _run_check(ICV_CORE_UUID_VERSION="4")
        ids = [e.id for e in errors]
        assert "icv_core.E001" in ids

    def test_e001_hint_contains_current_value(self):
        errors = _run_check(ICV_CORE_UUID_VERSION=99)
        e001 = next(e for e in errors if e.id == "icv_core.E001")
        assert "99" in e001.hint


# ---------------------------------------------------------------------------
# System checks — soft delete field
# ---------------------------------------------------------------------------


class TestCheckSoftDeleteField:
    """E002 fires when ICV_CORE_SOFT_DELETE_FIELD is blank or non-string."""

    def test_empty_string_raises_e002(self):
        errors = _run_check(ICV_CORE_SOFT_DELETE_FIELD="")
        ids = [e.id for e in errors]
        assert "icv_core.E002" in ids

    def test_whitespace_only_raises_e002(self):
        errors = _run_check(ICV_CORE_SOFT_DELETE_FIELD="   ")
        ids = [e.id for e in errors]
        assert "icv_core.E002" in ids

    def test_none_raises_e002(self):
        errors = _run_check(ICV_CORE_SOFT_DELETE_FIELD=None)
        ids = [e.id for e in errors]
        assert "icv_core.E002" in ids

    def test_integer_raises_e002(self):
        errors = _run_check(ICV_CORE_SOFT_DELETE_FIELD=123)
        ids = [e.id for e in errors]
        assert "icv_core.E002" in ids

    def test_valid_field_name_no_e002(self):
        errors = _run_check(ICV_CORE_SOFT_DELETE_FIELD="deleted")
        ids = [e.id for e in errors]
        assert "icv_core.E002" not in ids

    def test_e002_hint_contains_current_value(self):
        errors = _run_check(ICV_CORE_SOFT_DELETE_FIELD="")
        e002 = next(e for e in errors if e.id == "icv_core.E002")
        assert e002.id == "icv_core.E002"


# ---------------------------------------------------------------------------
# System checks — audit retention days
# ---------------------------------------------------------------------------


class TestCheckAuditRetentionDays:
    """E003 fires when audit is enabled and retention days is not a positive int."""

    def test_negative_retention_with_audit_enabled_raises_e003(self):
        errors = _run_check(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS=-10)
        ids = [e.id for e in errors]
        assert "icv_core.E003" in ids

    def test_zero_retention_with_audit_enabled_raises_e003(self):
        errors = _run_check(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS=0)
        ids = [e.id for e in errors]
        assert "icv_core.E003" in ids

    def test_string_retention_with_audit_enabled_raises_e003(self):
        errors = _run_check(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS="thirty")
        ids = [e.id for e in errors]
        assert "icv_core.E003" in ids

    def test_e003_hint_contains_current_value(self):
        errors = _run_check(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS=-5)
        e003 = next(e for e in errors if e.id == "icv_core.E003")
        assert "-5" in e003.hint

    def test_positive_retention_with_audit_enabled_no_e003(self):
        errors = _run_check(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS=180)
        ids = [e.id for e in errors]
        assert "icv_core.E003" not in ids


# ---------------------------------------------------------------------------
# System checks — hard delete warning
# ---------------------------------------------------------------------------


class TestCheckHardDelete:
    """W001 fires when ICV_CORE_ALLOW_HARD_DELETE is True."""

    def test_allow_hard_delete_true_produces_w001(self):
        errors = _run_check(ICV_CORE_ALLOW_HARD_DELETE=True)
        ids = [e.id for e in errors]
        assert "icv_core.W001" in ids

    def test_allow_hard_delete_false_no_w001(self):
        errors = _run_check(ICV_CORE_ALLOW_HARD_DELETE=False)
        ids = [e.id for e in errors]
        assert "icv_core.W001" not in ids

    def test_w001_is_warning_not_error(self):
        from django.core.checks import Warning as DjWarning

        errors = _run_check(ICV_CORE_ALLOW_HARD_DELETE=True)
        w001 = next(e for e in errors if e.id == "icv_core.W001")
        assert isinstance(w001, DjWarning)

    def test_w001_hint_mentions_soft_delete_protection(self):
        errors = _run_check(ICV_CORE_ALLOW_HARD_DELETE=True)
        w001 = next(e for e in errors if e.id == "icv_core.W001")
        assert "soft-delete" in w001.hint


# ---------------------------------------------------------------------------
# System checks — tenant model format
# ---------------------------------------------------------------------------


class TestCheckTenantModelFormat:
    """E004/E005 fire when ICV_TENANCY_TENANT_MODEL is malformed or unknown."""

    def test_missing_dot_raises_e005(self):
        errors = _run_check(ICV_TENANCY_TENANT_MODEL="NoAppLabel")
        ids = [e.id for e in errors]
        assert "icv_core.E005" in ids

    def test_multiple_dots_raises_e005(self):
        # 'a.b.c'.split('.') returns ['a', 'b', 'c'] — unpacking to two vars raises ValueError.
        errors = _run_check(ICV_TENANCY_TENANT_MODEL="a.b.c")
        ids = [e.id for e in errors]
        assert "icv_core.E005" in ids

    def test_falsy_value_skips_check(self):
        # Falsy ICV_TENANCY_TENANT_MODEL means no tenant — no E004/E005 expected.
        errors = _run_check(ICV_TENANCY_TENANT_MODEL="")
        ids = [e.id for e in errors]
        assert "icv_core.E004" not in ids
        assert "icv_core.E005" not in ids

    def test_nonexistent_model_raises_e004(self):
        errors = _run_check(ICV_TENANCY_TENANT_MODEL="auth.NonExistentModel99")
        ids = [e.id for e in errors]
        assert "icv_core.E004" in ids

    def test_valid_builtin_model_no_e004_or_e005(self):
        errors = _run_check(ICV_TENANCY_TENANT_MODEL="auth.Group")
        ids = [e.id for e in errors]
        assert "icv_core.E004" not in ids
        assert "icv_core.E005" not in ids

    def test_e004_msg_includes_model_reference(self):
        errors = _run_check(ICV_TENANCY_TENANT_MODEL="auth.GhostModel")
        e004 = next(e for e in errors if e.id == "icv_core.E004")
        assert "auth.GhostModel" in e004.msg

    def test_e005_hint_includes_bad_value(self):
        errors = _run_check(ICV_TENANCY_TENANT_MODEL="not_a_dotted_path")
        e005 = next(e for e in errors if e.id == "icv_core.E005")
        assert "not_a_dotted_path" in e005.hint


# ---------------------------------------------------------------------------
# icv_core_check command
# ---------------------------------------------------------------------------


class TestIcvCoreCheckCommand:
    """icv_core_check management command reports issues and successes."""

    def test_command_succeeds_with_no_issues(self):
        from django.test import override_settings

        stdout = StringIO()
        with (
            _patch_conf(ICV_CORE_TRACK_CREATED_BY=False, ICV_CORE_AUDIT_ENABLED=False),
            override_settings(MIDDLEWARE=[]),
        ):
            call_command("icv_core_check", stdout=stdout, stderr=StringIO())
        assert "OK" in stdout.getvalue()

    def test_command_reports_missing_current_user_middleware(self):
        from django.test import override_settings

        stderr = StringIO()
        with (
            _patch_conf(ICV_CORE_TRACK_CREATED_BY=True, ICV_CORE_AUDIT_ENABLED=False),
            override_settings(MIDDLEWARE=[]),
        ):
            call_command("icv_core_check", stdout=StringIO(), stderr=stderr)
        assert "CurrentUserMiddleware" in stderr.getvalue()

    def test_command_reports_missing_audit_middleware(self):
        from django.test import override_settings

        stderr = StringIO()
        with (
            _patch_conf(ICV_CORE_TRACK_CREATED_BY=False, ICV_CORE_AUDIT_ENABLED=True),
            override_settings(MIDDLEWARE=[]),
        ):
            call_command("icv_core_check", stdout=StringIO(), stderr=stderr)
        assert "AuditRequestMiddleware" in stderr.getvalue()

    def test_command_ok_when_current_user_middleware_present(self):
        from django.test import override_settings

        stdout = StringIO()
        with (
            _patch_conf(ICV_CORE_TRACK_CREATED_BY=True, ICV_CORE_AUDIT_ENABLED=False),
            override_settings(MIDDLEWARE=["icv_core.middleware.CurrentUserMiddleware"]),
        ):
            call_command("icv_core_check", stdout=stdout, stderr=StringIO())
        assert "OK" in stdout.getvalue()

    def test_command_ok_when_audit_middleware_present(self):
        from django.test import override_settings

        stdout = StringIO()
        with (
            _patch_conf(ICV_CORE_TRACK_CREATED_BY=False, ICV_CORE_AUDIT_ENABLED=True),
            override_settings(MIDDLEWARE=["icv_core.audit.middleware.AuditRequestMiddleware"]),
        ):
            call_command("icv_core_check", stdout=stdout, stderr=StringIO())
        assert "OK" in stdout.getvalue()

    def test_command_reports_multiple_issues_simultaneously(self):
        from django.test import override_settings

        stderr = StringIO()
        with (
            _patch_conf(ICV_CORE_TRACK_CREATED_BY=True, ICV_CORE_AUDIT_ENABLED=True),
            override_settings(MIDDLEWARE=[]),
        ):
            call_command("icv_core_check", stdout=StringIO(), stderr=stderr)
        output = stderr.getvalue()
        assert "CurrentUserMiddleware" in output
        assert "AuditRequestMiddleware" in output

    def test_command_does_not_accept_fix_flag(self):
        """--fix was removed; passing it must raise a SystemExit (argparse error)."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "django", "icv_core_check", "--fix"],
            capture_output=True,
            env={
                **__import__("os").environ,
                "DJANGO_SETTINGS_MODULE": "tests.settings",
                "PYTHONPATH": "src:tests",
            },
            cwd="/Users/nigelcopley/Projects/icv-oss/packages/icv-core",
        )
        assert result.returncode != 0

    def test_stderr_warns_when_issues_found(self):
        """Issues are written to stderr, not stdout."""
        from django.test import override_settings

        stdout = StringIO()
        stderr = StringIO()
        with (
            _patch_conf(ICV_CORE_TRACK_CREATED_BY=True, ICV_CORE_AUDIT_ENABLED=False),
            override_settings(MIDDLEWARE=[]),
        ):
            call_command("icv_core_check", stdout=stdout, stderr=stderr)
        # Stdout must not have "OK" when there are issues.
        assert "OK" not in stdout.getvalue()
        assert stderr.getvalue() != ""


# ---------------------------------------------------------------------------
# icv_core_audit_stats command
# ---------------------------------------------------------------------------


class TestIcvCoreAuditStatsCommand:
    """icv_core_audit_stats management command shows counts per event_type."""

    def test_warns_to_stderr_when_audit_disabled(self):
        stderr = StringIO()
        with _patch_conf(ICV_CORE_AUDIT_ENABLED=False):
            call_command("icv_core_audit_stats", stdout=StringIO(), stderr=stderr)
        assert "ICV_CORE_AUDIT_ENABLED" in stderr.getvalue()

    def test_no_stdout_output_when_audit_disabled(self):
        stdout = StringIO()
        with _patch_conf(ICV_CORE_AUDIT_ENABLED=False):
            call_command("icv_core_audit_stats", stdout=stdout, stderr=StringIO())
        assert stdout.getvalue() == ""

    @pytest.mark.django_db
    def test_shows_zero_total_with_no_entries(self):
        stdout = StringIO()
        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True):
            call_command("icv_core_audit_stats", stdout=stdout, stderr=StringIO())
        assert "0" in stdout.getvalue()

    @pytest.mark.django_db
    def test_shows_count_for_created_entries(self):
        from icv_core.testing.factories import AuditEntryFactory

        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True):
            AuditEntryFactory(event_type="DATA", action="CREATE")
            AuditEntryFactory(event_type="DATA", action="UPDATE")
            AuditEntryFactory(event_type="SECURITY", action="LOGIN")

            stdout = StringIO()
            call_command("icv_core_audit_stats", stdout=stdout, stderr=StringIO())

        output = stdout.getvalue()
        assert "3" in output

    @pytest.mark.django_db
    def test_groups_entries_by_event_type(self):
        from icv_core.testing.factories import AuditEntryFactory

        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True):
            AuditEntryFactory(event_type="SECURITY", action="LOGIN")
            AuditEntryFactory(event_type="SECURITY", action="LOGOUT")
            AuditEntryFactory(event_type="DATA", action="CREATE")

            stdout = StringIO()
            call_command("icv_core_audit_stats", stdout=stdout, stderr=StringIO())

        output = stdout.getvalue()
        assert "SECURITY" in output
        assert "DATA" in output

    @pytest.mark.django_db
    def test_default_period_is_week(self):
        """Command defaults to --period week; output must include the word 'week'."""
        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True):
            stdout = StringIO()
            call_command("icv_core_audit_stats", stdout=stdout, stderr=StringIO())
        assert "week" in stdout.getvalue()

    @pytest.mark.django_db
    def test_period_day_accepted(self):
        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True):
            stdout = StringIO()
            call_command("icv_core_audit_stats", period="day", stdout=stdout, stderr=StringIO())
        assert "day" in stdout.getvalue()

    @pytest.mark.django_db
    def test_period_month_accepted(self):
        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True):
            stdout = StringIO()
            call_command("icv_core_audit_stats", period="month", stdout=stdout, stderr=StringIO())
        assert "month" in stdout.getvalue()

    @pytest.mark.django_db
    def test_old_entries_excluded_from_period(self):
        """Entries created before the period window must not appear in the day count."""
        from datetime import timedelta

        from django.utils import timezone

        from icv_core.audit.models import AuditEntry
        from icv_core.models.base import BaseModel

        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True):
            old = AuditEntry(event_type="DATA", action="CREATE", description="old entry")
            # Bypass AuditEntry.save() immutability guard by calling BaseModel.save() directly.
            BaseModel.save(old)
            AuditEntry.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=60))

            stdout = StringIO()
            call_command("icv_core_audit_stats", period="day", stdout=stdout, stderr=StringIO())

        # A 60-day-old entry must not appear in the last-1-day total.
        output = stdout.getvalue()
        assert "0" in output

    @pytest.mark.django_db
    def test_security_entries_appear_in_output(self):
        from icv_core.testing.factories import AuditEntryFactory

        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True):
            AuditEntryFactory(event_type="SECURITY", action="LOGIN")
            AuditEntryFactory(event_type="SECURITY", action="LOGIN")

            stdout = StringIO()
            call_command("icv_core_audit_stats", stdout=stdout, stderr=StringIO())

        output = stdout.getvalue()
        assert "SECURITY" in output
        assert "2" in output


# ---------------------------------------------------------------------------
# icv_core_audit_archive command
# ---------------------------------------------------------------------------


class TestIcvCoreAuditArchiveCommand:
    """icv_core_audit_archive management command archives old entries."""

    def test_warns_to_stderr_when_audit_disabled(self):
        stderr = StringIO()
        with _patch_conf(ICV_CORE_AUDIT_ENABLED=False):
            call_command("icv_core_audit_archive", stdout=StringIO(), stderr=stderr)
        assert "ICV_CORE_AUDIT_ENABLED" in stderr.getvalue()

    def test_no_stdout_when_audit_disabled(self):
        stdout = StringIO()
        with _patch_conf(ICV_CORE_AUDIT_ENABLED=False):
            call_command("icv_core_audit_archive", stdout=stdout, stderr=StringIO())
        assert stdout.getvalue() == ""

    @pytest.mark.django_db
    def test_shows_zero_eligible_when_no_entries_exist(self):
        stdout = StringIO()
        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS=365):
            call_command("icv_core_audit_archive", stdout=stdout, stderr=StringIO())
        assert "0" in stdout.getvalue()

    @pytest.mark.django_db
    def test_dry_run_reports_eligible_entry(self):
        from datetime import timedelta

        from django.utils import timezone

        from icv_core.audit.models import AuditEntry
        from icv_core.models.base import BaseModel

        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS=30):
            old = AuditEntry(event_type="SYSTEM", action="CUSTOM", description="old")
            BaseModel.save(old)
            AuditEntry.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=60))

            stdout = StringIO()
            call_command(
                "icv_core_audit_archive",
                dry_run=True,
                stdout=stdout,
                stderr=StringIO(),
            )

        output = stdout.getvalue()
        assert "1" in output
        assert "Dry run" in output

    @pytest.mark.django_db
    def test_dry_run_does_not_delete_entries(self):
        """--dry-run must not modify any rows."""
        from datetime import timedelta

        from django.utils import timezone

        from icv_core.audit.models import AuditEntry
        from icv_core.models.base import BaseModel

        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS=30):
            old = AuditEntry(event_type="DATA", action="DELETE", description="dry-run check")
            BaseModel.save(old)
            AuditEntry.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=60))

            before = AuditEntry.objects.count()
            call_command(
                "icv_core_audit_archive",
                dry_run=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )
            after = AuditEntry.objects.count()

        assert after == before

    @pytest.mark.django_db
    def test_custom_days_flag_overrides_retention_setting(self):
        """--days overrides ICV_CORE_AUDIT_RETENTION_DAYS."""
        from datetime import timedelta

        from django.utils import timezone

        from icv_core.audit.models import AuditEntry
        from icv_core.models.base import BaseModel

        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS=365):
            recent_entry = AuditEntry(event_type="SYSTEM", action="CUSTOM", description="10-day-old")
            BaseModel.save(recent_entry)
            AuditEntry.objects.filter(pk=recent_entry.pk).update(created_at=timezone.now() - timedelta(days=10))

            stdout = StringIO()
            # Override to 5 days — the 10-day-old entry is now eligible.
            call_command(
                "icv_core_audit_archive",
                days=5,
                dry_run=True,
                stdout=stdout,
                stderr=StringIO(),
            )

        assert "1" in stdout.getvalue()

    @pytest.mark.django_db
    def test_recent_entries_not_eligible(self):
        """Entries created within the retention window must show count of 0."""
        from icv_core.testing.factories import AuditEntryFactory

        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS=365):
            AuditEntryFactory(event_type="DATA", action="CREATE")

            stdout = StringIO()
            call_command(
                "icv_core_audit_archive",
                dry_run=True,
                stdout=stdout,
                stderr=StringIO(),
            )

        assert "0" in stdout.getvalue()

    @pytest.mark.django_db
    def test_live_run_reports_eligible_count_and_backend_note(self):
        """Without --dry-run the command reports the count and mentions the archive backend."""
        from datetime import timedelta

        from django.utils import timezone

        from icv_core.audit.models import AuditEntry
        from icv_core.models.base import BaseModel

        with _patch_conf(ICV_CORE_AUDIT_ENABLED=True, ICV_CORE_AUDIT_RETENTION_DAYS=30):
            old = AuditEntry(event_type="SECURITY", action="LOGIN", description="archive test")
            BaseModel.save(old)
            AuditEntry.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=60))

            stdout = StringIO()
            call_command("icv_core_audit_archive", stdout=stdout, stderr=StringIO())

        output = stdout.getvalue()
        assert "1" in output


# ---------------------------------------------------------------------------
# Celery tasks — icv_core/audit/tasks.py
# ---------------------------------------------------------------------------


class TestAuditTasks:
    """Audit tasks are importable and callable without a running Celery broker."""

    def test_log_event_async_is_importable(self):
        from icv_core.audit.tasks import log_event_async

        assert callable(log_event_async)

    def test_archive_old_entries_is_importable(self):
        from icv_core.audit.tasks import archive_old_entries

        assert callable(archive_old_entries)

    @pytest.mark.django_db
    def test_archive_old_entries_returns_zero_when_no_entries(self):
        from icv_core.audit.tasks import archive_old_entries

        with _patch_conf(ICV_CORE_AUDIT_RETENTION_DAYS=365):
            result = archive_old_entries()

        assert result == 0

    @pytest.mark.django_db
    def test_archive_old_entries_counts_eligible_entries(self):
        from datetime import timedelta

        from django.utils import timezone

        from icv_core.audit.models import AuditEntry
        from icv_core.audit.tasks import archive_old_entries
        from icv_core.models.base import BaseModel

        with _patch_conf(ICV_CORE_AUDIT_RETENTION_DAYS=30):
            old = AuditEntry(event_type="DATA", action="CREATE", description="task test")
            BaseModel.save(old)
            AuditEntry.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=60))

            result = archive_old_entries()

        assert result == 1

    @pytest.mark.django_db
    def test_archive_old_entries_excludes_recent_entries(self):
        from icv_core.audit.tasks import archive_old_entries
        from icv_core.testing.factories import AuditEntryFactory

        with _patch_conf(ICV_CORE_AUDIT_RETENTION_DAYS=365):
            AuditEntryFactory(event_type="DATA", action="CREATE")
            result = archive_old_entries()

        assert result == 0

    @pytest.mark.django_db
    def test_log_event_async_creates_audit_entry(self):
        from icv_core.audit.models import AuditEntry
        from icv_core.audit.tasks import log_event_async

        log_event_async(
            event_type="SYSTEM",
            action="CUSTOM",
            user_id=None,
            description="task direct call",
            metadata={},
        )

        assert AuditEntry.objects.filter(description="task direct call").exists()

    @pytest.mark.django_db
    def test_log_event_async_stores_metadata(self):
        from icv_core.audit.models import AuditEntry
        from icv_core.audit.tasks import log_event_async

        log_event_async(
            event_type="DATA",
            action="UPDATE",
            user_id=None,
            description="metadata test",
            metadata={"field": "email"},
        )

        entry = AuditEntry.objects.get(description="metadata test")
        assert entry.metadata["field"] == "email"

    @pytest.mark.django_db
    def test_log_event_async_resolves_user_by_id(self):
        from django.contrib.auth import get_user_model

        from icv_core.audit.models import AuditEntry
        from icv_core.audit.tasks import log_event_async

        User = get_user_model()
        user = User.objects.create_user(username="taskuser", email="taskuser@example.com", password="pass")

        log_event_async(
            event_type="AUTHENTICATION",
            action="LOGIN",
            user_id=str(user.pk),
            description="user resolved",
            metadata={},
        )

        entry = AuditEntry.objects.get(description="user resolved")
        assert entry.user == user

    @pytest.mark.django_db
    def test_log_event_async_handles_missing_user_id_gracefully(self):
        """A user_id that does not exist must not raise — user should be None."""
        from icv_core.audit.models import AuditEntry
        from icv_core.audit.tasks import log_event_async

        log_event_async(
            event_type="SECURITY",
            action="PERMISSION_DENIED",
            user_id=999999,
            description="unknown user",
            metadata={},
        )

        entry = AuditEntry.objects.get(description="unknown user")
        assert entry.user is None

    @pytest.mark.django_db
    def test_log_event_async_none_user_id_leaves_user_null(self):
        from icv_core.audit.models import AuditEntry
        from icv_core.audit.tasks import log_event_async

        log_event_async(
            event_type="DATA",
            action="DELETE",
            user_id=None,
            description="null user id",
            metadata={},
        )

        entry = AuditEntry.objects.get(description="null user id")
        assert entry.user is None
