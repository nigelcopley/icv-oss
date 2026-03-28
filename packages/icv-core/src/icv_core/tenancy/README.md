# Tenancy Infrastructure

Row-level multi-tenant isolation for Django models.

## Overview

The tenancy infrastructure provides abstract mixins, managers, and context services for row-level tenant isolation. This allows Django models to be scoped to a tenant (organisation, workspace, team, etc.) whilst remaining in a single database schema.

**Schema-level tenancy** (via django-tenants) is configured entirely in the consuming project and does not require these tools.

## Components

### Context Management (`context.py`)

Thread-safe context variable management for the current tenant.

```python
from icv_core.tenancy import (
    get_current_tenant,
    set_current_tenant,
    clear_current_tenant,
    tenant_context,
)

# Set tenant (typically in middleware)
tenant = resolve_tenant_from_request(request)
set_current_tenant(tenant)

# Get tenant (in views, services, managers)
tenant = get_current_tenant()

# Temporary tenant context (Celery tasks, management commands)
with tenant_context(tenant):
    # All code in this block sees get_current_tenant() == tenant
    orders = Order.objects.for_tenant(get_current_tenant())

# Clear tenant
clear_current_tenant()
```

### Model Mixins (`mixins.py`)

#### `TenantAwareMixin`

Adds a `tenant` FK with `on_delete=PROTECT`. The tenant cannot be deleted whilst records exist.

```python
from icv_core.tenancy import TenantAwareMixin
from icv_core.models import BaseModel

class Product(TenantAwareMixin, BaseModel):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
```

#### `TenantOwnedMixin`

Adds a `tenant` FK with `on_delete=CASCADE`. Records are deleted when the tenant is deleted.

```python
from icv_core.tenancy import TenantOwnedMixin
from icv_core.models import BaseModel

class Invoice(TenantOwnedMixin, BaseModel):
    total = models.DecimalField(max_digits=10, decimal_places=2)
```

### Manager and QuerySet (`managers.py`)

Both mixins provide a `TenantScopedManager` as the default manager.

```python
# Filter by tenant
products = Product.objects.for_tenant(tenant)

# Chain with other filters
products = Product.objects.for_tenant(tenant).filter(price__gte=100)

# Filter active records (if model has is_active field)
products = Product.objects.for_tenant(tenant).active()
```

## Settings

### `ICV_TENANCY_TENANT_MODEL`

Type: `str`
Default: `"auth.Group"`

Swappable tenant model in dot-notation. Consuming projects override this.

```python
# settings.py
ICV_TENANCY_TENANT_MODEL = "icv_identity.Organisation"
```

### `ICV_TENANCY_ENFORCE_SCOPING`

Type: `bool`
Default: `False`

When `True` and `DEBUG=True`, raises an assertion if a query on a TenantAware model runs without `.for_tenant()` scope. This prevents accidental cross-tenant data leakage during development.

```python
# settings.py (development)
ICV_TENANCY_ENFORCE_SCOPING = DEBUG
```

## Usage Patterns

### In Middleware

Tenant resolution (from request headers, session, subdomain, membership) is handled by icv-identity's middleware. icv-core provides context STORAGE only.

```python
# icv_identity/middleware.py (example)
from icv_core.tenancy import set_current_tenant, clear_current_tenant

class TenantResolutionMiddleware:
    def __call__(self, request):
        tenant = resolve_tenant_from_request(request)
        set_current_tenant(tenant)
        response = self.get_response(request)
        clear_current_tenant()
        return response
```

### In Views

```python
from icv_core.tenancy import get_current_tenant

def product_list(request):
    tenant = get_current_tenant()
    products = Product.objects.for_tenant(tenant).filter(available=True)
    return render(request, "products/list.html", {"products": products})
```

### In Services

```python
from icv_core.tenancy import get_current_tenant

def create_invoice(total: Decimal) -> Invoice:
    """Create an invoice for the current tenant."""
    tenant = get_current_tenant()
    invoice = Invoice.objects.create(tenant=tenant, total=total)
    return invoice
```

### In Celery Tasks

```python
from icv_core.tenancy import tenant_context

@shared_task
def process_invoices_for_tenant(tenant_id: str):
    tenant = Tenant.objects.get(id=tenant_id)

    with tenant_context(tenant):
        invoices = Invoice.objects.for_tenant(get_current_tenant())
        for invoice in invoices:
            process_invoice(invoice)
```

### In Management Commands

```python
from django.core.management.base import BaseCommand
from icv_core.tenancy import tenant_context

class Command(BaseCommand):
    def handle(self, *args, **options):
        for tenant in Tenant.objects.all():
            with tenant_context(tenant):
                self.stdout.write(f"Processing {tenant.name}...")
                products = Product.objects.for_tenant(get_current_tenant())
                # ...
```

## Design Notes

### Row-Level vs Schema-Level

**Row-level tenancy** (this module):
- Single database schema
- All tenants share the same tables
- Tenant FK on every table
- Filtering via `.for_tenant()`
- Simpler migrations, easier backups
- Good for < 1000 tenants

**Schema-level tenancy** (django-tenants):
- Separate database schema per tenant
- No FK required
- Complete data isolation
- More complex migrations
- Good for regulatory compliance or large tenant counts

**icv-core does NOT choose between modes.** Consuming projects decide based on requirements. icv-identity's `ICV_IDENTITY_ISOLATION_STRATEGY` setting typically controls this.

### Why Not Auto-Filter?

The manager does NOT automatically filter by tenant. `.for_tenant()` must be called explicitly. This is intentional:

1. **Visibility**: Makes tenant scoping explicit in the code
2. **Safety**: Prevents hiding data unintentionally (queries that should be cross-tenant)
3. **Testing**: Makes it obvious when tests are missing tenant scoping

When `ICV_TENANCY_ENFORCE_SCOPING=True` and `DEBUG=True`, the framework raises assertions on unscoped queries (defence-in-depth during development).

### Field Name

The tenant FK field name is fixed as `"tenant"`. Consuming projects that need a different field name (e.g., `organisation`, `workspace`) should define the FK field explicitly rather than using these mixins.

## Testing

```python
import pytest
from django.contrib.auth.models import Group
from icv_core.tenancy import (
    TenantAwareMixin,
    get_current_tenant,
    set_current_tenant,
    tenant_context,
)

@pytest.fixture
def tenant(db):
    return Group.objects.create(name="Test Tenant")

def test_tenant_context_sets_current(tenant):
    with tenant_context(tenant):
        assert get_current_tenant() == tenant
```

## Related

- **Tenant model**: Defined in icv-identity (e.g., `Organisation`, `Tenant`)
- **Tenant resolution**: Handled by icv-identity middleware
- **Schema-level tenancy**: Configured via django-tenants in consuming project
