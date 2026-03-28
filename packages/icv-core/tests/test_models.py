"""Tests for icv-core abstract base models."""

import uuid

import pytest
from core_testapp.models import ConcreteBaseModel, ConcreteSoftDeleteModel
from django.db import models

from icv_core.models import BaseModel, SoftDeleteModel, TimestampedModel, UUIDModel


class TestUUIDModel:
    """UUIDModel provides a UUID primary key."""

    def test_has_uuid_primary_key(self):
        field = UUIDModel._meta.get_field("id")
        assert isinstance(field, models.UUIDField)
        assert field.primary_key is True
        assert field.editable is False

    def test_default_is_uuid4_callable(self):
        field = UUIDModel._meta.get_field("id")
        # default should be callable (uuid.uuid4)
        assert callable(field.default)

    def test_generated_pk_is_valid_uuid(self):
        field = ConcreteBaseModel._meta.get_field("id")
        value = field.default()
        assert isinstance(value, uuid.UUID)


class TestTimestampedModel:
    """TimestampedModel provides created_at and updated_at."""

    def test_has_created_at(self):
        field = TimestampedModel._meta.get_field("created_at")
        assert isinstance(field, models.DateTimeField)
        assert field.auto_now_add is True

    def test_has_updated_at(self):
        field = TimestampedModel._meta.get_field("updated_at")
        assert isinstance(field, models.DateTimeField)
        assert field.auto_now is True

    def test_created_at_has_db_index(self):
        field = TimestampedModel._meta.get_field("created_at")
        assert field.db_index is True


class TestBaseModel:
    """BaseModel combines UUID PK and timestamps."""

    def test_is_abstract(self):
        assert BaseModel._meta.abstract is True

    def test_has_uuid_pk(self):
        field = ConcreteBaseModel._meta.get_field("id")
        assert isinstance(field, models.UUIDField)
        assert field.primary_key is True

    def test_has_timestamps(self):
        assert ConcreteBaseModel._meta.get_field("created_at")
        assert ConcreteBaseModel._meta.get_field("updated_at")

    def test_default_ordering(self):
        # BaseModel's abstract Meta declares -created_at ordering.
        # Django 6.0+ does not propagate abstract Meta.ordering to concrete
        # subclasses that define their own Meta; verify on the abstract itself.
        assert BaseModel._meta.ordering == ["-created_at"]

    def test_inherits_uuid_and_timestamp(self):
        field_names = [f.name for f in ConcreteBaseModel._meta.fields]
        assert "id" in field_names
        assert "created_at" in field_names
        assert "updated_at" in field_names


class TestSoftDeleteModel:
    """SoftDeleteModel adds soft-delete behaviour to BaseModel."""

    def test_is_abstract(self):
        assert SoftDeleteModel._meta.abstract is True

    def test_has_is_active_field(self):
        field = ConcreteSoftDeleteModel._meta.get_field("is_active")
        assert isinstance(field, models.BooleanField)
        assert field.default is True
        assert field.db_index is True

    def test_has_deleted_at_field(self):
        field = ConcreteSoftDeleteModel._meta.get_field("deleted_at")
        assert isinstance(field, models.DateTimeField)
        assert field.null is True
        assert field.blank is True

    def test_has_soft_delete_manager(self):
        from icv_core.managers import SoftDeleteManager

        assert isinstance(ConcreteSoftDeleteModel.objects, SoftDeleteManager)

    def test_has_all_objects_manager(self):
        assert isinstance(ConcreteSoftDeleteModel.all_objects, models.Manager)

    @pytest.mark.django_db
    def test_soft_delete_sets_is_active_false(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        obj.soft_delete()
        obj.refresh_from_db()
        assert obj.is_active is False

    @pytest.mark.django_db
    def test_soft_delete_sets_deleted_at(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        assert obj.deleted_at is None
        obj.soft_delete()
        obj.refresh_from_db()
        assert obj.deleted_at is not None

    @pytest.mark.django_db
    def test_restore_sets_is_active_true(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        obj.soft_delete()
        obj.restore()
        obj.refresh_from_db()
        assert obj.is_active is True

    @pytest.mark.django_db
    def test_restore_clears_deleted_at(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        obj.soft_delete()
        obj.restore()
        obj.refresh_from_db()
        assert obj.deleted_at is None

    @pytest.mark.django_db
    def test_default_manager_excludes_soft_deleted(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()
        qs = ConcreteSoftDeleteModel.objects.all()
        assert active in qs
        assert deleted not in qs

    @pytest.mark.django_db
    def test_all_objects_includes_soft_deleted(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()
        qs = ConcreteSoftDeleteModel.all_objects.all()
        assert active in qs
        assert deleted in qs

    @pytest.mark.django_db
    def test_delete_raises_protected_error_by_default(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        with pytest.raises(models.ProtectedError):
            obj.delete()

    @pytest.mark.django_db
    def test_delete_allowed_when_setting_enabled(self, allow_hard_delete):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        obj_pk = obj.pk
        obj.delete()
        assert not ConcreteSoftDeleteModel.all_objects.filter(pk=obj_pk).exists()

    @pytest.mark.django_db
    def test_hard_delete_bypasses_protection(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        obj_pk = obj.pk
        obj.hard_delete()
        assert not ConcreteSoftDeleteModel.all_objects.filter(pk=obj_pk).exists()

    @pytest.mark.django_db
    def test_soft_delete_emits_signals(self):
        from icv_core.signals import post_soft_delete, pre_soft_delete

        pre_received = []
        post_received = []

        def on_pre(sender, instance, **kwargs):
            pre_received.append(instance)

        def on_post(sender, instance, **kwargs):
            post_received.append(instance)

        pre_soft_delete.connect(on_pre)
        post_soft_delete.connect(on_post)

        obj = ConcreteSoftDeleteModel.objects.create(title="signal-test")
        obj.soft_delete()

        pre_soft_delete.disconnect(on_pre)
        post_soft_delete.disconnect(on_post)

        assert len(pre_received) == 1
        assert len(post_received) == 1
        assert pre_received[0] is obj

    @pytest.mark.django_db
    def test_restore_emits_signals(self):
        from icv_core.signals import post_restore, pre_restore

        pre_received = []
        post_received = []

        def on_pre(sender, instance, **kwargs):
            pre_received.append(instance)

        def on_post(sender, instance, **kwargs):
            post_received.append(instance)

        pre_restore.connect(on_pre)
        post_restore.connect(on_post)

        obj = ConcreteSoftDeleteModel.objects.create(title="restore-signal-test")
        obj.soft_delete()
        obj.restore()

        pre_restore.disconnect(on_pre)
        post_restore.disconnect(on_post)

        assert len(pre_received) == 1
        assert len(post_received) == 1
