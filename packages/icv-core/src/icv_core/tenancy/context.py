"""Thread-safe context variable management for current tenant.

Provides storage for the current tenant in request-response cycle or async tasks.
Tenant RESOLUTION (from request headers, session, subdomain) is handled by
icv-identity's middleware. This module provides context STORAGE only.

Usage:
    # Set tenant (typically in middleware):
    from icv_core.tenancy import set_current_tenant
    set_current_tenant(tenant)

    # Get tenant (in views, services, managers):
    from icv_core.tenancy import get_current_tenant
    tenant = get_current_tenant()

    # Temporary tenant context (Celery tasks, management commands):
    from icv_core.tenancy import tenant_context
    with tenant_context(tenant):
        # All code in this block sees get_current_tenant() == tenant
        ...

    # Clear tenant:
    from icv_core.tenancy import clear_current_tenant
    clear_current_tenant()
"""

import contextvars
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

# Thread-safe context variable for storing the current tenant
_current_tenant: contextvars.ContextVar[Any | None] = contextvars.ContextVar("current_tenant", default=None)


def get_current_tenant() -> Any | None:
    """
    Retrieve the current tenant from context.

    Returns:
        The current tenant object, or None if no tenant is set.

    Example:
        tenant = get_current_tenant()
        if tenant:
            products = Product.objects.for_tenant(tenant)
    """
    return _current_tenant.get()


def set_current_tenant(tenant: Any) -> None:
    """
    Store the current tenant in context.

    Args:
        tenant: The tenant object to set as current. Can be any model instance
            matching ICV_TENANCY_TENANT_MODEL.

    Example:
        # In middleware:
        tenant = resolve_tenant_from_request(request)
        set_current_tenant(tenant)
    """
    _current_tenant.set(tenant)


def clear_current_tenant() -> None:
    """
    Clear the current tenant from context.

    Example:
        # At end of request cycle:
        clear_current_tenant()
    """
    _current_tenant.set(None)


@contextmanager
def tenant_context(tenant: Any) -> Generator[Any, None, None]:
    """
    Temporarily set a tenant for the duration of a context block.

    The previous tenant value is restored when exiting the context, even if an
    exception is raised.

    Args:
        tenant: The tenant to set for this context.

    Yields:
        The tenant that was set.

    Example:
        # In a Celery task:
        tenant = Tenant.objects.get(id=tenant_id)
        with tenant_context(tenant):
            # All queries in this block have access to get_current_tenant()
            orders = Order.objects.for_tenant(get_current_tenant())
            process_orders(orders)
        # Previous tenant value is restored here
    """
    token = _current_tenant.set(tenant)
    try:
        yield tenant
    finally:
        _current_tenant.reset(token)
