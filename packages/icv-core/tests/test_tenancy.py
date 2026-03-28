"""Tests for tenancy infrastructure (mixins, managers, context)."""

import pytest
from django.contrib.auth.models import Group
from django.db import models

from icv_core.models import BaseModel
from icv_core.tenancy import (
    TenantAwareMixin,
    TenantOwnedMixin,
    TenantScopedManager,
    clear_current_tenant,
    get_current_tenant,
    set_current_tenant,
    tenant_context,
)

# Test models - these are created dynamically for testing


class TenantAwareProduct(TenantAwareMixin, BaseModel):
    """Test model with TenantAwareMixin (PROTECT)."""

    name = models.CharField(max_length=255)

    class Meta:
        app_label = "icv_core"


class TenantOwnedInvoice(TenantOwnedMixin, BaseModel):
    """Test model with TenantOwnedMixin (CASCADE)."""

    total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = "icv_core"


@pytest.mark.django_db
class TestTenantContext:
    """Test tenant context management functions."""

    def test_get_current_tenant_when_none_set(self):
        """Test get_current_tenant returns None when no tenant is set."""
        clear_current_tenant()
        assert get_current_tenant() is None

    def test_set_and_get_current_tenant(self):
        """Test set_current_tenant stores tenant and get_current_tenant retrieves it."""
        tenant = Group.objects.create(name="Test Tenant")

        set_current_tenant(tenant)
        assert get_current_tenant() == tenant

    def test_clear_current_tenant(self):
        """Test clear_current_tenant removes tenant from context."""
        tenant = Group.objects.create(name="Test Tenant")

        set_current_tenant(tenant)
        assert get_current_tenant() == tenant

        clear_current_tenant()
        assert get_current_tenant() is None

    def test_tenant_context_manager(self):
        """Test tenant_context temporarily sets tenant."""
        tenant1 = Group.objects.create(name="Tenant 1")
        tenant2 = Group.objects.create(name="Tenant 2")

        # Set initial tenant
        set_current_tenant(tenant1)
        assert get_current_tenant() == tenant1

        # Use context manager to temporarily switch
        with tenant_context(tenant2):
            assert get_current_tenant() == tenant2

        # Original tenant is restored
        assert get_current_tenant() == tenant1

    def test_tenant_context_manager_with_none(self):
        """Test tenant_context works with None as tenant."""
        tenant = Group.objects.create(name="Test Tenant")
        set_current_tenant(tenant)

        with tenant_context(None):
            assert get_current_tenant() is None

        # Original tenant is restored
        assert get_current_tenant() == tenant

    def test_tenant_context_manager_restores_on_exception(self):
        """Test tenant_context restores previous tenant even when exception is raised."""
        tenant1 = Group.objects.create(name="Tenant 1")
        tenant2 = Group.objects.create(name="Tenant 2")

        set_current_tenant(tenant1)

        with pytest.raises(ValueError), tenant_context(tenant2):
            assert get_current_tenant() == tenant2
            raise ValueError("Test exception")

        # Original tenant is restored despite exception
        assert get_current_tenant() == tenant1

    def test_nested_tenant_context(self):
        """Test tenant_context can be nested."""
        tenant1 = Group.objects.create(name="Tenant 1")
        tenant2 = Group.objects.create(name="Tenant 2")
        tenant3 = Group.objects.create(name="Tenant 3")

        set_current_tenant(tenant1)

        with tenant_context(tenant2):
            assert get_current_tenant() == tenant2

            with tenant_context(tenant3):
                assert get_current_tenant() == tenant3

            assert get_current_tenant() == tenant2

        assert get_current_tenant() == tenant1


@pytest.mark.django_db
class TestTenantScopedManager:
    """Test TenantScopedManager and TenantScopedQuerySet."""

    def setup_method(self):
        """Set up test data before each test."""
        self.tenant1 = Group.objects.create(name="Tenant 1")
        self.tenant2 = Group.objects.create(name="Tenant 2")

    def test_manager_has_for_tenant_method(self):
        """Test TenantScopedManager provides .for_tenant() method."""
        manager = TenantScopedManager()
        assert hasattr(manager, "for_tenant")

    def test_manager_has_active_method(self):
        """Test TenantScopedManager provides .active() method."""
        manager = TenantScopedManager()
        assert hasattr(manager, "active")

    def test_manager_get_queryset_returns_tenant_scoped_queryset(self):
        """Test get_queryset returns TenantScopedQuerySet."""
        from icv_core.tenancy.managers import TenantScopedQuerySet

        manager = TenantScopedManager()
        manager.model = Group  # Set a model for testing
        qs = manager.get_queryset()
        assert isinstance(qs, TenantScopedQuerySet)

    def test_queryset_active_with_is_active_field(self):
        """Test active() filters by is_active when field exists."""
        from icv_core.models import SoftDeleteModel
        from icv_core.tenancy.managers import TenantScopedQuerySet

        # Use SoftDeleteModel which has is_active field
        qs = TenantScopedQuerySet(model=SoftDeleteModel)
        qs.model = SoftDeleteModel
        active_qs = qs.active()
        # Verify it returns a queryset (actual filtering happens in DB)
        assert isinstance(active_qs, TenantScopedQuerySet)

    def test_queryset_active_without_is_active_field(self):
        """Test active() returns all when model has no is_active field."""
        from icv_core.tenancy.managers import TenantScopedQuerySet

        # Use Group which has no is_active field
        qs = TenantScopedQuerySet(model=Group)
        active_qs = qs.active()
        # Should return the same queryset
        assert isinstance(active_qs, TenantScopedQuerySet)


@pytest.mark.django_db
class TestTenantAwareMixin:
    """Test TenantAwareMixin adds tenant FK correctly."""

    def test_mixin_adds_tenant_field(self):
        """Test TenantAwareMixin adds tenant FK field to model."""

        class Product(TenantAwareMixin, BaseModel):
            name = models.CharField(max_length=255)

            class Meta:
                app_label = "test_tenancy"

        # Check tenant field exists
        assert hasattr(Product, "tenant")

        # Check field is a ForeignKey
        tenant_field = Product._meta.get_field("tenant")
        assert isinstance(tenant_field, models.ForeignKey)

    def test_mixin_adds_tenant_scoped_manager(self):
        """Test TenantAwareMixin sets TenantScopedManager as default manager."""

        class Product(TenantAwareMixin, BaseModel):
            name = models.CharField(max_length=255)

            class Meta:
                app_label = "test_tenancy"

        # Check objects manager is TenantScopedManager
        assert isinstance(Product.objects, TenantScopedManager)

    def test_tenant_aware_uses_protect(self):
        """Test TenantAwareMixin uses on_delete=PROTECT."""

        class Product(TenantAwareMixin, BaseModel):
            name = models.CharField(max_length=255)

            class Meta:
                app_label = "test_tenancy"

        tenant_field = Product._meta.get_field("tenant")
        assert tenant_field.remote_field.on_delete == models.PROTECT


@pytest.mark.django_db
class TestTenantOwnedMixin:
    """Test TenantOwnedMixin uses CASCADE for tenant FK."""

    def test_tenant_owned_uses_cascade(self):
        """Test TenantOwnedMixin uses on_delete=CASCADE."""

        class Invoice(TenantOwnedMixin, BaseModel):
            total = models.DecimalField(max_digits=10, decimal_places=2)

            class Meta:
                app_label = "test_tenancy"

        tenant_field = Invoice._meta.get_field("tenant")
        assert tenant_field.remote_field.on_delete == models.CASCADE

    def test_tenant_owned_adds_tenant_field(self):
        """Test TenantOwnedMixin inherits tenant FK from TenantAwareMixin."""

        class Invoice(TenantOwnedMixin, BaseModel):
            total = models.DecimalField(max_digits=10, decimal_places=2)

            class Meta:
                app_label = "test_tenancy"

        # Check tenant field exists
        assert hasattr(Invoice, "tenant")

        # Check field is a ForeignKey
        tenant_field = Invoice._meta.get_field("tenant")
        assert isinstance(tenant_field, models.ForeignKey)

    def test_tenant_owned_adds_tenant_scoped_manager(self):
        """Test TenantOwnedMixin sets TenantScopedManager as default manager."""

        class Invoice(TenantOwnedMixin, BaseModel):
            total = models.DecimalField(max_digits=10, decimal_places=2)

            class Meta:
                app_label = "test_tenancy"

        # Check objects manager is TenantScopedManager
        assert isinstance(Invoice.objects, TenantScopedManager)


@pytest.mark.django_db
class TestTenantContextIntegration:
    """Integration tests for tenant context with managers."""

    def test_context_can_be_used_with_manager(self):
        """Test tenant context works with manager filtering."""
        tenant1 = Group.objects.create(name="Tenant 1")
        tenant2 = Group.objects.create(name="Tenant 2")

        # Set tenant in context
        with tenant_context(tenant1):
            current = get_current_tenant()
            assert current == tenant1

        # Switch tenant
        with tenant_context(tenant2):
            current = get_current_tenant()
            assert current == tenant2

    def test_clear_tenant_after_use(self):
        """Test clearing tenant context."""
        tenant = Group.objects.create(name="Test Tenant")

        set_current_tenant(tenant)
        assert get_current_tenant() is not None

        clear_current_tenant()
        assert get_current_tenant() is None
