"""Vocabulary lifecycle services for icv-taxonomy.

Handles creation, update, and deletion of Vocabulary instances. Slug
collision resolution and type-immutability guards live here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.utils.text import slugify

from ..exceptions import TaxonomyValidationError

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_slug(name: str, base_slug: str, model_cls: type) -> str:
    """Return a unique slug for a vocabulary.

    Args:
        name: Human-readable name used as the slug source when base_slug is blank.
        base_slug: Caller-supplied slug; if blank, derived from name.
        model_cls: The concrete Vocabulary model class.

    Returns:
        A slug that does not collide with any existing vocabulary.

    Side effects:
        None (read-only DB query).
    """
    from ..conf import get_setting

    slug_max = get_setting("ICV_TAXONOMY_SLUG_MAX_LENGTH", 255)
    case_sensitive = get_setting("ICV_TAXONOMY_CASE_SENSITIVE_SLUGS", False)

    candidate = base_slug or slugify(name)
    if not case_sensitive:
        candidate = candidate.lower()
    candidate = candidate[:slug_max]

    if not model_cls.all_objects.filter(slug=candidate).exists():
        return candidate

    counter = 2
    while True:
        suffix = f"-{counter}"
        truncated = candidate[: slug_max - len(suffix)]
        numbered = truncated + suffix
        if not model_cls.all_objects.filter(slug=numbered).exists():
            return numbered
        counter += 1


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def create_vocabulary(
    name: str,
    slug: str = "",
    vocabulary_type: str = "flat",
    **kwargs: Any,
) -> Any:
    """Create and persist a new Vocabulary instance.

    Slugs are auto-generated from ``name`` when ``slug`` is blank, with
    numeric suffixes appended on collision (BR-TAX-043). The
    ``vocabulary_created`` signal is emitted by the post-save handler wired
    in ``handlers.py`` — this function does not emit it directly.

    Args:
        name: Human-readable vocabulary name (e.g., "Colours").
        slug: Machine-readable slug. Auto-generated from name if blank.
        vocabulary_type: One of ``"flat"``, ``"hierarchical"``, or
            ``"faceted"``. Defaults to ``"flat"``.
        **kwargs: Any additional field values accepted by the Vocabulary model
            (e.g., ``description``, ``is_open``, ``allow_multiple``,
            ``max_depth``, ``metadata``).

    Returns:
        The newly created Vocabulary instance.

    Raises:
        TaxonomyValidationError: If the model's ``full_clean()`` raises.

    Side effects:
        Inserts a row into the vocabulary table.
        Emits ``vocabulary_created`` via post-save handler.
    """
    from ..conf import get_vocabulary_model

    Vocabulary = get_vocabulary_model()
    resolved_slug = _resolve_slug(name, slug, Vocabulary)

    vocabulary = Vocabulary(
        name=name,
        slug=resolved_slug,
        vocabulary_type=vocabulary_type,
        **kwargs,
    )
    vocabulary.full_clean()
    vocabulary.save()
    return vocabulary


def update_vocabulary(vocabulary: Any, **kwargs: Any) -> Any:
    """Update mutable fields on an existing Vocabulary instance.

    Validates that ``vocabulary_type`` is not changed once terms exist
    (BR-TAX-002, defence-in-depth — model's ``clean()`` also enforces this).

    Args:
        vocabulary: The Vocabulary instance to update.
        **kwargs: Field name → new value pairs. Only provided fields are
            updated; others are left unchanged.

    Returns:
        The updated Vocabulary instance (same object, mutated in-place and
        re-saved).

    Raises:
        TaxonomyValidationError: If attempting to change ``vocabulary_type``
            when terms already exist.

    Side effects:
        Updates the vocabulary row in the database.
    """
    new_type = kwargs.get("vocabulary_type")
    if new_type is not None and new_type != vocabulary.vocabulary_type and vocabulary.terms.exists():
        raise TaxonomyValidationError("Cannot change vocabulary_type once terms exist (BR-TAX-002).")

    for field, value in kwargs.items():
        setattr(vocabulary, field, value)

    update_fields = list(kwargs.keys())
    if update_fields:
        vocabulary.full_clean()
        vocabulary.save(update_fields=update_fields)
    return vocabulary


def clear_vocabulary(vocabulary: Any, *, emit_signals: bool = False) -> int:
    """Delete all terms in a vocabulary without deleting the vocabulary itself.

    Uses a single bulk DELETE that cascades to term relationships and
    associations via database CASCADE constraints.

    Args:
        vocabulary: Vocabulary instance to clear.
        emit_signals: When True, explicitly emit term_deleted for each term
            before the bulk DELETE. Default False. Note: Django's ORM also
            fires pre_delete (and therefore the term_deleted handler) per
            instance during queryset deletion regardless of this flag; this
            parameter controls whether the service emits an *additional*
            explicit signal before the delete, giving callers early notice
            with controlled keyword arguments.

    Returns:
        Number of terms deleted.

    Side effects:
        Deletes all Term rows for the vocabulary and all cascaded rows
        (TermAssociation, TermRelationship).
        When emit_signals=True, emits ``term_deleted`` for each term before
        the bulk delete.
    """
    from ..conf import get_term_model
    from ..signals import term_deleted

    Term = get_term_model()
    qs = Term.all_objects.filter(vocabulary=vocabulary)

    if emit_signals:
        for term in qs:
            term_deleted.send(
                sender=Term,
                term=term,
                vocabulary=vocabulary,
            )

    deleted_count, _ = qs.delete()
    return deleted_count


def delete_vocabulary(vocabulary: Any) -> None:
    """Delete a Vocabulary and all its related terms and associations.

    Cascade deletion of terms, associations, and relationships is handled
    by the database via ``on_delete=CASCADE``. The ``vocabulary_deleted``
    signal is emitted by the pre-delete handler wired in ``handlers.py``.

    Args:
        vocabulary: The Vocabulary instance to delete.

    Returns:
        None

    Raises:
        Nothing raised by this function directly; database or handler errors
        may propagate.

    Side effects:
        Deletes the vocabulary row and all cascaded rows.
        Emits ``vocabulary_deleted`` via pre-delete handler.
    """
    vocabulary.delete()
