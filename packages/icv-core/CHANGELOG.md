# Changelog

All notable changes to django-icv-core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
