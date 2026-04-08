"""Abstract base models for all ICV-Django packages."""

import logging
import os
import time
import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def _uuid7() -> uuid.UUID:
    """
    Generate a UUID version 7 value per RFC 9562.

    Layout (128 bits):
      unix_ts_ms  — 48 bits  — milliseconds since Unix epoch
      ver         —  4 bits  — version = 0b0111 (7)
      rand_a      — 12 bits  — random
      var         —  2 bits  — variant = 0b10
      rand_b      — 62 bits  — random

    Python 3.12 does not include uuid.uuid7(); this implementation uses only
    the stdlib uuid and os modules.
    """
    ms = int(time.time() * 1000) & 0xFFFF_FFFF_FFFF  # 48-bit timestamp
    rand = int.from_bytes(os.urandom(10), "big")  # 80 random bits
    rand_a = (rand >> 68) & 0xFFF  # upper 12 bits
    rand_b = rand & 0x3FFF_FFFF_FFFF_FFFF  # lower 62 bits

    hi = (ms << 16) | 0x7000 | rand_a  # 64 bits: ts + ver + rand_a
    lo = 0x8000_0000_0000_0000 | rand_b  # 64 bits: var + rand_b

    return uuid.UUID(int=(hi << 64) | lo)


def _make_uuid() -> uuid.UUID:
    """
    Return a UUID whose version is determined by ``ICV_CORE_UUID_VERSION``.

    The setting is read at call time so that test overrides via ``pytest``
    ``settings`` fixtures take effect without requiring a module reload.
    """
    from icv_core.conf import get_setting

    version = get_setting("UUID_VERSION", 4)
    if version == 7:
        return _uuid7()
    return uuid.uuid4()


class UUIDModel(models.Model):
    """Abstract model providing a UUID primary key."""

    id = models.UUIDField(
        primary_key=True,
        default=_make_uuid,
        editable=False,
        verbose_name=_("ID"),
    )

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    """Abstract model with auto-managed created_at and updated_at timestamps."""

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("created at"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("updated at"),
    )

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimestampedModel):
    """
    Standard base model combining a UUID primary key and auto-managed timestamps.

    All ICV-Django concrete models should inherit from this unless there is a
    specific reason not to (e.g., an append-only log table that must not have
    updated_at).
    """

    class Meta:
        abstract = True
        ordering = ["-created_at"]
