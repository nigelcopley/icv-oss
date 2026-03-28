"""Concrete model implementations used in icv-core tests."""

from django.db import models

from icv_core.audit.mixins import AuditMixin
from icv_core.models import BaseModel, SoftDeleteModel


class ConcreteBaseModel(BaseModel):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "core_testapp"


class ConcreteSoftDeleteModel(SoftDeleteModel):
    title = models.CharField(max_length=100)

    class Meta:
        app_label = "core_testapp"


class ConcreteAuditModel(AuditMixin, BaseModel):
    """Minimal concrete model for testing AuditMixin behaviour."""

    label = models.CharField(max_length=100)

    class Meta:
        app_label = "core_testapp"
