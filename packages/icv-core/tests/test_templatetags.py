"""Tests for icv-core template tags and filters."""

from datetime import timedelta

from django.utils import timezone


class TestCentsToCurrency:
    """cents_to_currency filter formats pence as a currency string."""

    def _apply(self, value, currency="GBP"):
        from icv_core.templatetags.icv_core import cents_to_currency

        return cents_to_currency(value, currency)

    def test_gbp_formatting(self):
        assert self._apply(3500, "GBP") == "£35.00"

    def test_eur_formatting(self):
        assert self._apply(3500, "EUR") == "€35.00"

    def test_usd_formatting(self):
        assert self._apply(3500, "USD") == "$35.00"

    def test_unknown_currency_uses_code_as_symbol(self):
        result = self._apply(100, "SEK")
        assert result == "SEK1.00"

    def test_zero_value(self):
        assert self._apply(0, "GBP") == "£0.00"

    def test_pence_rounding(self):
        assert self._apply(99, "GBP") == "£0.99"


class TestCentsToAmount:
    """cents_to_amount filter converts pence to decimal string."""

    def _apply(self, value):
        from icv_core.templatetags.icv_core import cents_to_amount

        return cents_to_amount(value)

    def test_basic_conversion(self):
        assert self._apply(3500) == "35.00"

    def test_zero(self):
        assert self._apply(0) == "0.00"

    def test_odd_pence(self):
        assert self._apply(1) == "0.01"


class TestTimeSinceShort:
    """time_since_short filter returns human-readable time strings."""

    def _apply(self, dt):
        from icv_core.templatetags.icv_core import time_since_short

        return time_since_short(dt)

    def test_just_now(self):
        result = self._apply(timezone.now() - timedelta(seconds=30))
        assert result == "just now"

    def test_minutes_ago(self):
        result = self._apply(timezone.now() - timedelta(minutes=5))
        assert "5m ago" in result

    def test_hours_ago(self):
        result = self._apply(timezone.now() - timedelta(hours=3))
        assert "3h ago" in result

    def test_days_ago(self):
        result = self._apply(timezone.now() - timedelta(days=4))
        assert "4d ago" in result

    def test_months_ago(self):
        result = self._apply(timezone.now() - timedelta(days=60))
        assert "mo ago" in result

    def test_years_ago(self):
        result = self._apply(timezone.now() - timedelta(days=400))
        assert "y ago" in result
