"""Term relationship services for icv-taxonomy.

Handles creation, deletion, and querying of TermRelationship instances.
Bidirectional relationship types (``synonym``, ``related``) automatically
create reciprocal records (BR-TAX-020).
"""

from __future__ import annotations

from typing import Any

from ..exceptions import TaxonomyValidationError

# Relationship types that require a reciprocal record (BR-TAX-020).
_BIDIRECTIONAL_TYPES = frozenset({"synonym", "related"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_relationship_model() -> type:
    """Return the TermRelationship model, resolved at call time.

    Returns:
        The TermRelationship model class.
    """
    from django.apps import apps

    return apps.get_model("icv_taxonomy", "TermRelationship")


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def add_relationship(
    term_from: Any,
    term_to: Any,
    relationship_type: str,
) -> Any:
    """Create a semantic relationship between two terms.

    For bidirectional types (``synonym``, ``related``), also creates the
    reciprocal record (BR-TAX-020). Self-relationships are forbidden
    (BR-TAX-021).

    Args:
        term_from: The source Term.
        term_to: The target Term.
        relationship_type: One of the TermRelationship.RelationshipType
            values: ``"synonym"``, ``"related"``, ``"see_also"``,
            ``"broader"``, ``"narrower"``.

    Returns:
        The primary TermRelationship instance (term_from → term_to).

    Raises:
        TaxonomyValidationError: If term_from and term_to are the same term
            (BR-TAX-021).

    Side effects:
        Inserts one or two TermRelationship rows (reciprocal for bidirectional
        types).
    """
    if term_from.pk == term_to.pk:
        raise TaxonomyValidationError("A term cannot have a relationship with itself (BR-TAX-021).")

    TermRelationship = _get_relationship_model()

    relationship, _ = TermRelationship.objects.get_or_create(
        term_from=term_from,
        term_to=term_to,
        relationship_type=relationship_type,
    )

    # Create reciprocal for bidirectional types (BR-TAX-020).
    if relationship_type in _BIDIRECTIONAL_TYPES:
        TermRelationship.objects.get_or_create(
            term_from=term_to,
            term_to=term_from,
            relationship_type=relationship_type,
        )

    return relationship


def remove_relationship(
    term_from: Any,
    term_to: Any,
    relationship_type: str,
) -> None:
    """Remove a semantic relationship between two terms.

    For bidirectional types, also removes the reciprocal record.

    Args:
        term_from: The source Term.
        term_to: The target Term.
        relationship_type: The relationship type to remove.

    Returns:
        None

    Side effects:
        Deletes one or two TermRelationship rows.
    """
    TermRelationship = _get_relationship_model()

    TermRelationship.objects.filter(
        term_from=term_from,
        term_to=term_to,
        relationship_type=relationship_type,
    ).delete()

    if relationship_type in _BIDIRECTIONAL_TYPES:
        TermRelationship.objects.filter(
            term_from=term_to,
            term_to=term_from,
            relationship_type=relationship_type,
        ).delete()


def get_related_terms(
    term: Any,
    relationship_type: str | None = None,
) -> Any:
    """Return terms that are related to the given term (outgoing relationships).

    Args:
        term: The source Term to query relationships from.
        relationship_type: Optional filter to restrict to a single relationship
            type. When None, all outgoing relationships are included.

    Returns:
        A QuerySet of related Term instances (the ``term_to`` side of matching
        TermRelationship rows).

    Side effects:
        None (pure read).
    """
    from ..conf import get_term_model

    TermRelationship = _get_relationship_model()
    Term = get_term_model()

    qs = TermRelationship.objects.filter(term_from=term)
    if relationship_type is not None:
        qs = qs.filter(relationship_type=relationship_type)

    term_ids = qs.values_list("term_to_id", flat=True)
    return Term.all_objects.filter(pk__in=term_ids)


def get_synonyms(term: Any) -> Any:
    """Return all synonym terms for the given term.

    Convenience wrapper around ``get_related_terms(term, "synonym")``.

    Args:
        term: The Term to retrieve synonyms for.

    Returns:
        A QuerySet of Term instances that are synonyms of ``term``.

    Side effects:
        None (pure read).
    """
    return get_related_terms(term, "synonym")
