"""Custom exceptions for icv-core."""


class ImmutableRecordError(Exception):
    """Raised when attempting to update an immutable record (e.g., AuditEntry)."""

    pass
