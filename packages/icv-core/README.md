# django-icv-core

[![CI](https://github.com/nigelcopley/icv-oss/actions/workflows/ci.yml/badge.svg)](https://github.com/nigelcopley/icv-oss/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/django-icv-core.svg)](https://pypi.org/project/django-icv-core/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-icv-core.svg)](https://pypi.org/project/django-icv-core/)
[![Django versions](https://img.shields.io/pypi/djversions/django-icv-core.svg)](https://pypi.org/project/django-icv-core/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Foundation layer for ICV-Django packages. Provides abstract base models,
custom managers, middleware, utilities, template tags, and an optional audit
subsystem.

## Installation

```bash
pip install django-icv-core
```

```python
INSTALLED_APPS = [
    # ...
    "icv_core",
]
```

## Quick Start

```python
from icv_core.models import BaseModel, SoftDeleteModel

class Article(BaseModel):
    title = models.CharField(max_length=255)

class Product(SoftDeleteModel):
    name = models.CharField(max_length=255)

# Soft delete
product.soft_delete()   # sets is_active=False, deleted_at=now
product.restore()       # sets is_active=True, deleted_at=None

# Filtered queries
Product.objects.all()          # active only
Product.objects.deleted()      # soft-deleted only
Product.all_objects.all()      # everything
```

## Settings

All settings use the `ICV_CORE_` prefix. Every setting has a sensible default.

| Setting | Default | Description |
|---------|---------|-------------|
| `ICV_CORE_UUID_VERSION` | `4` | UUID version for primary keys |
| `ICV_CORE_ALLOW_HARD_DELETE` | `False` | Allow `.delete()` on SoftDeleteModel |
| `ICV_CORE_TRACK_CREATED_BY` | `False` | Enable created_by/updated_by tracking |
| `ICV_CORE_AUDIT_ENABLED` | `False` | Enable the audit subsystem |
| `ICV_CORE_AUDIT_RETENTION_DAYS` | `365` | Days before audit entries are eligible for archival |

See the source code in `icv_core/conf.py` for the full settings reference.
