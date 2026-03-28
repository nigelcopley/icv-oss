"""
icv_core.audit — Audit subsystem for icv-core.

Active only when ICV_CORE_AUDIT_ENABLED=True. Provides:
- AuditEntry, AdminActivityLog, SystemAlert concrete models
- AuditMixin for automatic model change tracking
- AuditRequestMiddleware for request context capture
- log_event() service function
- @audited decorator
- Celery task for archiving old entries
- DRF API viewsets (admin-only)
"""
