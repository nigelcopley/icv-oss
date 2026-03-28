"""Exceptions for icv-taxonomy."""

from __future__ import annotations

from django.core.exceptions import ValidationError


class TaxonomyError(Exception):
    """Base exception for all icv-taxonomy errors."""


class TaxonomyValidationError(TaxonomyError, ValidationError):
    """Raised when taxonomy data fails business-rule validation.

    Inherits from both TaxonomyError (for catch-by-package) and
    Django's ValidationError (for form/serialiser integration).
    """
