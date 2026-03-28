# django-icv-core

[![CI](https://github.com/nigelcopley/icv-oss/actions/workflows/ci.yml/badge.svg)](https://github.com/nigelcopley/icv-oss/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/django-icv-core.svg)](https://pypi.org/project/django-icv-core/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-icv-core.svg)](https://pypi.org/project/django-icv-core/)
[![Django versions](https://img.shields.io/pypi/djversions/django-icv-core.svg)](https://pypi.org/project/django-icv-core/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

`django-icv-core` is the foundation layer for the ICV Django ecosystem. It gives every model in your project a UUID primary key, auto-managed timestamps, and optional soft-delete behaviour — with zero boilerplate. Add the optional audit subsystem and you get immutable event logs, admin activity tracking, and system alerts with a single setting.

Use it as a standalone package or as the base for other `django-icv-*` packages.

---

## Features

- **`BaseModel`** — UUID primary key (v4 by default, v7 opt-in) and auto-managed `created_at`/`updated_at` timestamps
- **`SoftDeleteModel`** — Safe record removal with `soft_delete()` and `restore()`; default manager excludes deleted records automatically
- **`SoftDeleteManager` / `SoftDeleteQuerySet`** — `.active()`, `.deleted()`, `.with_deleted()` on every soft-delete model
- **`CurrentUserMiddleware`** — Thread-local request user for automatic `created_by`/`updated_by` population
- **Audit subsystem** (opt-in via `ICV_CORE_AUDIT_ENABLED`) — Immutable `AuditEntry`, `AdminActivityLog`, `SystemAlert`, `AuditMixin`, `@audited` decorator, and management commands
- **Template tags** — `cents_to_currency`, `cents_to_amount`, `time_since_short`
- **Django system checks** — Configuration validation at startup
- **Test utilities** — `icv_core.testing` provides factory-boy factories and pytest fixtures for consuming projects

---

## Requirements

- Python 3.11+
- Django 4.2, 5.0, or 5.1

---

## Installation

```bash
pip install django-icv-core
```

Add `icv_core` to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "icv_core",
]
```

Run migrations:

```bash
python manage.py migrate
```

> **Note:** The audit subsystem tables are only created when `ICV_CORE_AUDIT_ENABLED = True`. Add `django.contrib.contenttypes` to `INSTALLED_APPS` before enabling audit.

---

## Quick Start

### BaseModel — UUID primary keys and timestamps

Inherit from `BaseModel` and every record gets a UUID primary key and automatic timestamps. No extra fields to define.

```python
from django.db import models
from icv_core.models import BaseModel


class Article(BaseModel):
    title = models.CharField(max_length=255)
    body = models.TextField()

    class Meta(BaseModel.Meta):
        verbose_name_plural = "articles"
```

```python
article = Article.objects.create(title="Hello, world", body="...")

article.id          # UUID4: e.g. '3f2504e0-4f89-11d3-9a0c-0305e82c3301'
article.created_at  # datetime — set on creation, never changes
article.updated_at  # datetime — updated automatically on every save
```

---

### SoftDeleteModel — safe record removal

Records are never hard-deleted by default. `soft_delete()` sets `is_active=False` and records the timestamp. The default manager silently excludes deleted records from all queries.

```python
from icv_core.models import SoftDeleteModel


class Subscription(SoftDeleteModel):
    plan = models.CharField(max_length=50)
    customer_email = models.EmailField()
```

```python
sub = Subscription.objects.create(plan="pro", customer_email="user@example.com")

# Soft-delete: hides the record from default queries
sub.soft_delete()
sub.is_active   # False
sub.deleted_at  # datetime

# Default manager returns active records only
Subscription.objects.all()          # excludes deleted records
Subscription.objects.active()       # same as above — explicit alias

# Access deleted or all records when needed
Subscription.objects.deleted()      # deleted records only
Subscription.objects.with_deleted() # everything
Subscription.all_objects.all()      # raw manager — no filtering applied

# Restore
sub.restore()
sub.is_active   # True
sub.deleted_at  # None
```

Hard deletion is blocked unless you explicitly allow it:

```python
# Raises ProtectedError by default
sub.delete()

# Permanent removal — use deliberately
sub.hard_delete()

# Or allow .delete() project-wide
ICV_CORE_ALLOW_HARD_DELETE = True
```

---

### CurrentUserMiddleware — automatic created_by/updated_by

Add the middleware to make the current request user available to models without passing it through every service call.

```python
# settings.py
MIDDLEWARE = [
    # ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "icv_core.middleware.CurrentUserMiddleware",  # must come after AuthenticationMiddleware
    # ...
]

ICV_CORE_TRACK_CREATED_BY = True
```

```python
from icv_core.middleware import get_current_user

user = get_current_user()  # returns None outside of a request context
```

---

### Audit subsystem

Enable the audit subsystem in settings:

```python
ICV_CORE_AUDIT_ENABLED = True
```

**`AuditEntry`** — an immutable record of a system event. Raises `ImmutableRecordError` on update and `ProtectedError` on delete.

```python
from icv_core.audit.services import log_event
from icv_core.audit.models import AuditEntry

# Record a security event
log_event(
    event_type=AuditEntry.EventType.SECURITY,
    action=AuditEntry.Action.PERMISSION_DENIED,
    user=request.user,
    description="Attempted access to restricted resource.",
    metadata={"path": request.path},
)
```

**`AuditMixin`** — add to any model to track CREATE, UPDATE, and DELETE automatically:

```python
from icv_core.audit.mixins import AuditMixin
from icv_core.models import BaseModel


class Contract(AuditMixin, BaseModel):
    title = models.CharField(max_length=255)
    value = models.DecimalField(max_digits=10, decimal_places=2)
```

**`@audited` decorator** — wrap a view or service function to record its execution:

```python
from icv_core.audit.decorators import audited
from icv_core.audit.models import AuditEntry


@audited(event_type=AuditEntry.EventType.DATA, action=AuditEntry.Action.DELETE)
def cancel_membership(user, membership):
    membership.soft_delete()
```

**`SystemAlert`** — raise and resolve operational alerts:

```python
from icv_core.audit.services import raise_alert, resolve_alert
from icv_core.audit.models import SystemAlert

alert = raise_alert(
    alert_type=SystemAlert.AlertType.PAYMENT,
    severity="error",
    title="Payment processor unreachable",
    message="Stripe API returned 503 for the last 5 minutes.",
)

# Later, once resolved
resolve_alert(alert, resolved_by=request.user, notes="Stripe incident resolved.")
```

---

### Template tags

```django
{% load icv_core %}

{# Format pence/cents as a currency string #}
{{ order.total_pence|cents_to_currency:"GBP" }}  {# £35.00 #}
{{ order.total_pence|cents_to_currency:"USD" }}  {# $35.00 #}

{# Raw decimal amount without currency symbol #}
{{ order.total_pence|cents_to_amount }}           {# 35.00 #}

{# Short human-readable relative time #}
{{ comment.created_at|time_since_short }}         {# 2h ago / 3d ago / just now #}
```

---

## Settings reference

All settings use the `ICV_CORE_` prefix. Every setting has a sensible default — only override what you need.

### Core

| Setting | Default | Description |
|---|---|---|
| `ICV_CORE_UUID_VERSION` | `4` | UUID version for primary keys. `4` = random; `7` = time-sorted (requires Python 3.12+) |
| `ICV_CORE_SOFT_DELETE_FIELD` | `"is_active"` | Field name used for soft-delete filtering |
| `ICV_CORE_ALLOW_HARD_DELETE` | `False` | When `True`, `.delete()` performs a hard delete on `SoftDeleteModel` instead of raising `ProtectedError` |
| `ICV_CORE_TRACK_CREATED_BY` | `False` | Enable `created_by`/`updated_by` tracking. Requires `CurrentUserMiddleware` |
| `ICV_CORE_DEFAULT_ORDERING` | `"-created_at"` | Default ordering applied to `BaseModel` subclasses |

### Audit

| Setting | Default | Description |
|---|---|---|
| `ICV_CORE_AUDIT_ENABLED` | `False` | Master switch. No tables are created and no signals connect when `False` |
| `ICV_CORE_AUDIT_RETENTION_DAYS` | `365` | Days before audit entries are eligible for archival |
| `ICV_CORE_AUDIT_EXCLUDE_MODELS` | `[]` | Models excluded from `AuditMixin` auto-tracking. Format: `["app_label.ModelName"]` |
| `ICV_CORE_AUDIT_TRACK_FIELD_CHANGES` | `True` | Capture old and new field values on UPDATE |
| `ICV_CORE_AUDIT_CAPTURE_IP` | `True` | Record the request IP address in audit entries |
| `ICV_CORE_AUDIT_CAPTURE_USER_AGENT` | `True` | Record the request user agent in audit entries |
| `ICV_CORE_AUDIT_AUTO_MODEL_TRACKING` | `False` | Automatically log CREATE/UPDATE/DELETE on all `BaseModel` subclasses |
| `ICV_CORE_AUDIT_ALERT_SEVERITY_LEVELS` | `["info", "warning", "error", "critical"]` | Available severity levels for `SystemAlert` |

---

## Management commands

| Command | Description |
|---|---|
| `icv_core_check` | Validate package configuration and emit any warnings |
| `icv_core_audit_archive` | Archive audit entries older than `ICV_CORE_AUDIT_RETENTION_DAYS` |
| `icv_core_audit_stats` | Print a summary of audit entry counts by event type and action |

---

## Testing utilities

`icv_core.testing` provides factory-boy factories and pytest fixtures for use in your own project's test suite.

```python
# In your tests
from icv_core.testing.factories import AuditEntryFactory, SystemAlertFactory

entry = AuditEntryFactory(action="CREATE", event_type="DATA")
alert = SystemAlertFactory(severity="critical", alert_type="payment")
```

Import the included pytest fixtures by adding `icv_core.testing.fixtures` to your `conftest.py`:

```python
# conftest.py
pytest_plugins = ["icv_core.testing.fixtures"]
```

---

## Signals

`icv-core` emits the following signals. Connect to them from your own apps for loose coupling.

| Signal | Sent when |
|---|---|
| `icv_core.signals.pre_soft_delete` | Before a record is soft-deleted |
| `icv_core.signals.post_soft_delete` | After a record is soft-deleted |
| `icv_core.signals.pre_restore` | Before a soft-deleted record is restored |
| `icv_core.signals.post_restore` | After a soft-deleted record is restored |
| `icv_core.audit.signals.audit_entry_created` | After an `AuditEntry` is written |
| `icv_core.audit.signals.system_alert_raised` | After a `SystemAlert` is raised |
| `icv_core.audit.signals.system_alert_resolved` | After a `SystemAlert` is resolved |

---

## Licence

MIT — see [LICENSE](LICENSE).
