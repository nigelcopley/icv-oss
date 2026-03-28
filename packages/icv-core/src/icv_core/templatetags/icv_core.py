"""
Template tags and filters for icv-core.

Usage::

    {% load icv_core %}
    {{ value|cents_to_currency:"GBP" }}
    {{ value|cents_to_amount }}
    {{ timestamp|time_since_short }}
"""

import decimal
from datetime import datetime

from django import template
from django.utils import timezone
from django.utils.translation import gettext as _

register = template.Library()


@register.filter
def cents_to_currency(value: int, currency_code: str = "GBP") -> str:
    """
    Format an integer number of pence/cents as a currency string.

    Example::

        {{ 3500|cents_to_currency:"GBP" }}  →  £35.00
        {{ 3500|cents_to_currency:"EUR" }}  →  €35.00
        {{ 3500|cents_to_currency:"USD" }}  →  $35.00
    """
    symbols = {"GBP": "£", "EUR": "€", "USD": "$"}
    symbol = symbols.get(currency_code.upper(), currency_code)
    amount = decimal.Decimal(value) / 100
    return f"{symbol}{amount:.2f}"


@register.filter
def cents_to_amount(value: int) -> str:
    """
    Convert an integer number of pence/cents to a decimal amount string.

    Example::

        {{ 3500|cents_to_amount }}  →  35.00
    """
    amount = decimal.Decimal(value) / 100
    return f"{amount:.2f}"


@register.filter
def time_since_short(value: datetime) -> str:
    """
    Return a short human-readable time-since string.

    Example::

        {{ booking.created_at|time_since_short }}  →  2h ago / just now / 3d ago
    """
    now = timezone.now()
    if isinstance(value, datetime) and timezone.is_naive(value):
        value = timezone.make_aware(value)

    diff = now - value
    seconds = int(diff.total_seconds())

    if seconds < 60:
        return _("just now")
    if seconds < 3600:
        minutes = seconds // 60
        return _("%(count)dm ago") % {"count": minutes}
    if seconds < 86400:
        hours = seconds // 3600
        return _("%(count)dh ago") % {"count": hours}
    days = diff.days
    if days < 30:
        return _("%(count)dd ago") % {"count": days}
    if days < 365:
        months = days // 30
        return _("%(count)dmo ago") % {"count": months}
    years = days // 365
    return _("%(count)dy ago") % {"count": years}
