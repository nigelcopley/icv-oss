"""Tests for icv-core custom managers."""

import pytest
from core_testapp.models import ConcreteSoftDeleteModel


class TestSoftDeleteManager:
    """SoftDeleteManager filters correctly."""

    @pytest.mark.django_db
    def test_active_returns_only_active(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()

        result = ConcreteSoftDeleteModel.objects.active()
        assert active in result
        assert deleted not in result

    @pytest.mark.django_db
    def test_deleted_returns_only_deleted(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()

        result = ConcreteSoftDeleteModel.objects.deleted()
        assert deleted in result
        assert active not in result

    @pytest.mark.django_db
    def test_with_deleted_returns_all(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()

        result = ConcreteSoftDeleteModel.objects.with_deleted()
        assert active in result
        assert deleted in result


class TestSoftDeleteQuerySet:
    """SoftDeleteQuerySet chaining works correctly."""

    @pytest.mark.django_db
    def test_queryset_active_chained(self):
        ConcreteSoftDeleteModel.objects.create(title="a")
        ConcreteSoftDeleteModel.objects.create(title="b")

        # Default manager already filters active; active() is an alias
        qs = ConcreteSoftDeleteModel.objects.active()
        assert qs.count() == 2

    @pytest.mark.django_db
    def test_queryset_deleted_chained(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="x")
        obj.soft_delete()

        qs = ConcreteSoftDeleteModel.objects.deleted()
        assert qs.count() == 1
