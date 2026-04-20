"""
Admin classes for icv-taxonomy.

Provides:
  VocabularyAdmin     — admin for the Vocabulary model
  TermAdmin           — admin for the Term model (with TreeAdmin mixin)
  TermRelationshipInline — inline for TermRelationship on TermAdmin

Models are resolved lazily via get_vocabulary_model() / get_term_model() from
conf.py so that swapped models are handled correctly.
"""

from __future__ import annotations

from django.contrib import admin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

try:
    from icv_tree.admin import TreeAdmin as _TreeAdmin
except ImportError:
    _TreeAdmin = None  # type: ignore[assignment, misc]


# ---------------------------------------------------------------------------
# Inline
# ---------------------------------------------------------------------------


def _build_term_relationship_inline():  # type: ignore[no-untyped-def]
    """Build and return a TermRelationshipInline class bound to the model.

    Created lazily so that the TermRelationship model is resolved at call time
    (after Django's app registry is ready) rather than at import time.
    """
    from django.apps import apps

    try:
        TermRelationship = apps.get_model("icv_taxonomy", "TermRelationship")
    except LookupError:
        return None

    class _TermRelationshipInline(admin.TabularInline):
        model = TermRelationship
        fk_name = "term_from"
        fields = ("term_to", "relationship_type")
        autocomplete_fields = ("term_to",)
        extra = 1

        def get_queryset(self, request):  # type: ignore[no-untyped-def]
            return super().get_queryset(request).select_related("term_to", "term_to__vocabulary")

    return _TermRelationshipInline


# ---------------------------------------------------------------------------
# VocabularyAdmin
# ---------------------------------------------------------------------------


class VocabularyAdmin(admin.ModelAdmin):
    """Admin for the Vocabulary model."""

    list_display = ("name", "slug", "vocabulary_type", "is_open", "term_count", "is_active")
    list_filter = ("vocabulary_type", "is_open", "is_active")
    search_fields = ("name", "slug")

    def get_readonly_fields(self, request, obj=None):  # type: ignore[no-untyped-def]
        base = list(super().get_readonly_fields(request, obj))
        base += ["created_at", "updated_at"]
        return base

    def get_fieldsets(self, request, obj=None):  # type: ignore[no-untyped-def]
        return [
            (
                _("General"),
                {
                    "fields": ("name", "slug", "description"),
                },
            ),
            (
                _("Configuration"),
                {
                    "fields": ("vocabulary_type", "is_open", "allow_multiple", "max_depth"),
                },
            ),
            (
                _("Metadata"),
                {
                    "fields": ("metadata", "is_active"),
                },
            ),
            (
                _("Timestamps"),
                {
                    "classes": ("collapse",),
                    "fields": ("created_at", "updated_at"),
                },
            ),
        ]

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        """Annotate queryset with active term count."""
        related_name = _get_term_related_name()
        return (
            super()
            .get_queryset(request)
            .annotate(_term_count=Count(related_name, filter=_active_terms_filter(related_name)))
        )

    @admin.display(description=_("Terms"), ordering="_term_count")
    def term_count(self, obj) -> int:  # type: ignore[no-untyped-def]
        """Return count of active terms in this vocabulary."""
        return getattr(obj, "_term_count", 0)


# ---------------------------------------------------------------------------
# TermAdmin — composed with TreeAdmin when available
# ---------------------------------------------------------------------------

_term_admin_bases: tuple = (_TreeAdmin, admin.ModelAdmin) if _TreeAdmin is not None else (admin.ModelAdmin,)


class TermAdmin(*_term_admin_bases):  # type: ignore[misc]
    """Admin for the Term model.

    Inherits TreeAdmin from icv-tree when installed, falling back to a flat
    ModelAdmin when icv-tree is absent (should not occur in practice since
    icv-tree is a hard dependency, but the guard prevents import errors in
    unusual test environments).
    """

    list_display = ("indented_title", "slug", "vocabulary", "is_active")
    list_filter = ("vocabulary", "is_active", "depth")
    list_select_related = ("vocabulary",)
    search_fields = ("name", "slug")
    autocomplete_fields = ("vocabulary", "parent")

    def get_readonly_fields(self, request, obj=None):  # type: ignore[no-untyped-def]
        return ["path", "depth", "order", "created_at", "updated_at"]

    def get_fieldsets(self, request, obj=None):  # type: ignore[no-untyped-def]
        return [
            (
                _("General"),
                {
                    "fields": ("vocabulary", "name", "slug", "description", "parent"),
                },
            ),
            (
                _("Tree"),
                {
                    "classes": ("collapse",),
                    "fields": ("path", "depth", "order"),
                },
            ),
            (
                _("Metadata"),
                {
                    "fields": ("metadata", "is_active"),
                },
            ),
            (
                _("Timestamps"),
                {
                    "classes": ("collapse",),
                    "fields": ("created_at", "updated_at"),
                },
            ),
        ]

    def get_inlines(self, request, obj):  # type: ignore[no-untyped-def]
        """Build and return TermRelationshipInline lazily."""
        inline_class = _build_term_relationship_inline()
        if inline_class is None:
            return []
        return [inline_class]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def _get_term_related_name() -> str:
    """Return the reverse relation name from Vocabulary to the Term model.

    Resolves dynamically so that custom Term subclasses with ``%(class)s_set``
    related_name patterns work correctly (e.g. ``term_set`` for the default
    Term model, ``productterm_set`` for a custom ProductTerm subclass).
    """
    from .conf import get_term_model

    Term = get_term_model()
    return f"{Term.__name__.lower()}_set"


def _active_terms_filter(related_name: str | None = None):  # type: ignore[no-untyped-def]
    """Return a Q object filtering terms to is_active=True.

    Kept as a function to defer import of django.db.models.Q until needed.
    """
    from django.db.models import Q

    if related_name is None:
        related_name = _get_term_related_name()
    return Q(**{f"{related_name}__is_active": True})


def _register_admin() -> None:
    """Register VocabularyAdmin and TermAdmin with the default site.

    Wrapped in a function and guarded by try/except so that misconfigured
    or swapped models do not break the whole admin at startup.
    """
    from .conf import get_term_model, get_vocabulary_model

    try:
        Vocabulary = get_vocabulary_model()
        admin.site.register(Vocabulary, VocabularyAdmin)
    except Exception:  # noqa: BLE001
        pass

    try:
        Term = get_term_model()
        admin.site.register(Term, TermAdmin)
    except Exception:  # noqa: BLE001
        pass


_register_admin()
