"""Tests for icv-core signal definitions."""

from django.dispatch import Signal

from icv_core.signals import post_restore, post_soft_delete, pre_restore, pre_soft_delete


class TestSignalDefinitions:
    """Core signals are correctly defined."""

    def test_pre_soft_delete_is_signal(self):
        assert isinstance(pre_soft_delete, Signal)

    def test_post_soft_delete_is_signal(self):
        assert isinstance(post_soft_delete, Signal)

    def test_pre_restore_is_signal(self):
        assert isinstance(pre_restore, Signal)

    def test_post_restore_is_signal(self):
        assert isinstance(post_restore, Signal)
