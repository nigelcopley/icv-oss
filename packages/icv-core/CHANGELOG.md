# Changelog

All notable changes to django-icv-core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.2.0] - 2026-04-08

Promoted to Production/Stable.

### Added

- `ComplianceModel.save()` auto-populates `created_by` (on insert) and
  `updated_by` (on every save) from `CurrentUserMiddleware` when
  `ICV_CORE_TRACK_CREATED_BY` is True. Explicit values are preserved.
- UUID v7 support (RFC 9562) — when `ICV_CORE_UUID_VERSION=7`,
  `UUIDModel` generates time-sortable UUIDs using a pure-stdlib
  implementation. No third-party dependency required.
- 28 new tests for ComplianceModel auto-population and UUID v7

### Removed

- Unused `--fix` flag from `icv_core_check` management command

## [0.1.0] - 2026-03-14

### Added

- Abstract base models: `UUIDModel`, `TimestampedModel`, `BaseModel`, `SoftDeleteModel`, `ComplianceModel`
- Custom managers: `SoftDeleteManager` with `deleted()` and `with_deleted()` querysets
- `ScopedManager` for generic filtered queries
- `CurrentUserMiddleware` for `created_by`/`updated_by` tracking
- Soft-delete signals: `pre_soft_delete`, `post_soft_delete`, `pre_restore`, `post_restore`
- `IcvSoftDeleteAdmin` mixin for Django admin
- Package settings via `conf.py` with `ICV_CORE_*` namespace
- Template tags: `cents_to_currency`, `cents_to_amount`, `time_since_short`
- Audit subsystem (gated by `ICV_CORE_AUDIT_ENABLED`):
  - Concrete models: `AuditEntry`, `AdminActivityLog`, `SystemAlert`
  - `AuditMixin` for automatic model change tracking
  - `AuditRequestMiddleware` for request context capture
  - Audit services: `log_event()`, `raise_alert()`, `resolve_alert()`
  - `@audited` decorator for views and service functions
  - Django auth signal handlers (login, logout, login_failed)
  - DRF API viewsets (staff-only)
  - Management commands: `icv_core_check`, `icv_core_audit_archive`, `icv_core_audit_stats`
- Django system checks for configuration validation
- Test utilities: `icv_core.testing` with factories, fixtures, and helpers
- Comprehensive test suite with 90%+ coverage
