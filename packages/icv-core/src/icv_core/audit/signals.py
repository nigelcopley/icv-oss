"""Signal definitions for the icv-core audit subsystem."""

from django.dispatch import Signal

# Fired after a new AuditEntry is saved; provides: instance
audit_entry_created = Signal()

# Fired after a new SystemAlert is created; provides: instance
system_alert_raised = Signal()

# Fired after a SystemAlert is resolved; provides: instance, resolved_by
system_alert_resolved = Signal()
