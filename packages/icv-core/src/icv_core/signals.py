"""Signal definitions for icv-core."""

from django.dispatch import Signal

# Soft-delete lifecycle signals
pre_soft_delete = Signal()  # Sent before soft_delete() executes; provides: instance
post_soft_delete = Signal()  # Sent after soft_delete() completes; provides: instance
pre_restore = Signal()  # Sent before restore() executes; provides: instance
post_restore = Signal()  # Sent after restore() completes; provides: instance
