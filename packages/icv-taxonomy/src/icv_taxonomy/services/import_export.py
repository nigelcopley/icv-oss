"""Import/export services for icv-taxonomy.

Provides vocabulary serialisation to/from a self-contained dict suitable
for JSON storage and transmission (BR-TAX-030). Import is idempotent by
slug (BR-TAX-031) and respects closed vocabulary status (BR-TAX-032).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from ..exceptions import TaxonomyValidationError

# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def export_vocabulary(
    vocabulary: Any,
    include_inactive: bool = False,
) -> dict:
    """Serialise a vocabulary and all its terms/relationships to a dict.

    Produces a JSON-serialisable document sufficient to reconstruct the
    vocabulary via ``import_vocabulary()`` (BR-TAX-030). Terms are ordered
    depth-first by ``path``. Relationships are included only where both
    terms are within the vocabulary.

    Args:
        vocabulary: The Vocabulary instance to export.
        include_inactive: When True, include inactive terms in the export.
            Defaults to False (active terms only).

    Returns:
        A JSON-serialisable dict with structure::

            {
                "name": str,
                "slug": str,
                "description": str,
                "vocabulary_type": str,
                "is_open": bool,
                "allow_multiple": bool,
                "max_depth": int or None,
                "metadata": dict,
                "terms": [
                    {
                        "name": str,
                        "slug": str,
                        "description": str,
                        "parent_slug": str or None,
                        "is_active": bool,
                        "metadata": dict,
                    },
                    ...
                ],
                "relationships": [
                    {
                        "term_from_slug": str,
                        "term_to_slug": str,
                        "relationship_type": str,
                    },
                    ...
                ],
            }

    Side effects:
        None (pure read).
    """
    from ..conf import get_term_model

    Term = get_term_model()

    if include_inactive:
        terms_qs = Term.all_objects.filter(vocabulary=vocabulary).select_related("parent").order_by("path")
    else:
        terms_qs = (
            Term.all_objects.filter(vocabulary=vocabulary, is_active=True).select_related("parent").order_by("path")
        )

    # Build a slug → term mapping for relationship export.
    term_slug_set = {t.slug for t in terms_qs}

    serialised_terms = []
    for term in terms_qs:
        parent_slug: str | None = None
        if term.parent_id is not None:
            # Resolve parent slug without an extra query.
            parent_slug = term.parent.slug if term.parent is not None else None

        serialised_terms.append(
            {
                "name": term.name,
                "slug": term.slug,
                "description": term.description,
                "parent_slug": parent_slug,
                "is_active": term.is_active,
                "metadata": term.metadata if hasattr(term, "metadata") else {},
            }
        )

    # Export relationships where both endpoints are within the vocabulary.
    from django.apps import apps

    TermRelationship = apps.get_model("icv_taxonomy", "TermRelationship")

    # Fetch all relationships where term_from is in this vocabulary.
    relationship_qs = TermRelationship.objects.filter(
        term_from__vocabulary=vocabulary,
        term_to__vocabulary=vocabulary,
    ).select_related("term_from", "term_to")

    if not include_inactive:
        relationship_qs = relationship_qs.filter(
            term_from__is_active=True,
            term_to__is_active=True,
        )

    serialised_relationships = []
    for rel in relationship_qs:
        if rel.term_from.slug in term_slug_set and rel.term_to.slug in term_slug_set:
            serialised_relationships.append(
                {
                    "term_from_slug": rel.term_from.slug,
                    "term_to_slug": rel.term_to.slug,
                    "relationship_type": rel.relationship_type,
                }
            )

    return {
        "name": vocabulary.name,
        "slug": vocabulary.slug,
        "description": vocabulary.description,
        "vocabulary_type": vocabulary.vocabulary_type,
        "is_open": vocabulary.is_open,
        "allow_multiple": vocabulary.allow_multiple,
        "max_depth": vocabulary.max_depth,
        "metadata": vocabulary.metadata if hasattr(vocabulary, "metadata") else {},
        "terms": serialised_terms,
        "relationships": serialised_relationships,
    }


def import_vocabulary(
    data: dict,
    vocabulary: Any | None = None,
) -> dict:
    """Import a vocabulary from a serialised dict, idempotent by slug.

    When ``vocabulary`` is None, creates a new vocabulary from the data's
    metadata. When provided, imports terms into the existing vocabulary.

    Terms are matched by ``slug`` within the vocabulary (BR-TAX-031) —
    existing terms are updated, new slugs create new terms, and absent
    slugs are left untouched (additive import).

    Raises ``TaxonomyValidationError`` if the target vocabulary is closed
    and the import data contains new term slugs (BR-TAX-032).

    Wrapped in ``transaction.atomic``.

    Args:
        data: A dict in the format produced by ``export_vocabulary()``.
        vocabulary: Optional existing Vocabulary to import into. When None,
            a new vocabulary is created from ``data["slug"]`` and metadata.

    Returns:
        A dict with import statistics::

            {"created": int, "updated": int, "skipped": int}

    Raises:
        TaxonomyValidationError: If the target vocabulary is closed and new
            terms would be created, or if model validation fails.

    Side effects:
        Creates or updates vocabulary and term rows.
        Creates relationship rows (idempotent via get_or_create).
    """
    from ..conf import get_term_model, get_vocabulary_model
    from .relationships import add_relationship
    from .term_management import create_term, update_term
    from .vocabulary_management import create_vocabulary

    created = 0
    updated = 0
    skipped = 0

    with transaction.atomic():
        Vocabulary = get_vocabulary_model()
        Term = get_term_model()

        # --- Step 1: Resolve or create vocabulary ---
        if vocabulary is None:
            vocab_slug = data.get("slug", "")
            try:
                vocabulary = Vocabulary.all_objects.get(slug=vocab_slug)
                # Update mutable vocabulary metadata.
                _vocab_update_fields = {}
                for field in ("name", "description", "allow_multiple", "max_depth", "metadata"):
                    if field in data:
                        _vocab_update_fields[field] = data[field]
                if _vocab_update_fields:
                    for f, v in _vocab_update_fields.items():
                        setattr(vocabulary, f, v)
                    vocabulary.save(update_fields=list(_vocab_update_fields.keys()))
            except Vocabulary.DoesNotExist:
                vocabulary = create_vocabulary(
                    name=data.get("name", vocab_slug),
                    slug=vocab_slug,
                    vocabulary_type=data.get("vocabulary_type", "flat"),
                    description=data.get("description", ""),
                    is_open=data.get("is_open", True),
                    allow_multiple=data.get("allow_multiple", True),
                    max_depth=data.get("max_depth"),
                    metadata=data.get("metadata", {}),
                )

        terms_data: list[dict] = data.get("terms", [])

        # BR-TAX-032: Closed vocabulary must not receive new term slugs.
        if not vocabulary.is_open:
            existing_slugs = set(Term.all_objects.filter(vocabulary=vocabulary).values_list("slug", flat=True))
            new_slugs = {t["slug"] for t in terms_data if t["slug"] not in existing_slugs}
            if new_slugs:
                raise TaxonomyValidationError(
                    f"Vocabulary '{vocabulary.slug}' is closed. Import would create "
                    f"new terms: {', '.join(sorted(new_slugs))} (BR-TAX-032)."
                )

        # --- Step 2: Build slug → term map for existing terms ---
        existing_terms: dict[str, Any] = {t.slug: t for t in Term.all_objects.filter(vocabulary=vocabulary)}

        # --- Step 3: Import terms in path order (parents before children) ---
        # We rely on the export's depth-first path ordering: parents always
        # appear before their children in the terms list.
        imported_terms: dict[str, Any] = dict(existing_terms)

        for term_data in terms_data:
            slug = term_data["slug"]
            name = term_data.get("name", slug)
            description = term_data.get("description", "")
            parent_slug = term_data.get("parent_slug")
            is_active = term_data.get("is_active", True)
            metadata = term_data.get("metadata", {})

            parent: Any | None = None
            if parent_slug is not None:
                parent = imported_terms.get(parent_slug)
                if parent is None:
                    # Parent not yet imported — skip and rely on caller to
                    # re-sort or accept the partial import.
                    skipped += 1
                    continue

            if slug in existing_terms:
                term = existing_terms[slug]
                update_term(
                    term,
                    name=name,
                    description=description,
                    is_active=is_active,
                    metadata=metadata,
                )
                imported_terms[slug] = term
                updated += 1
            else:
                term = create_term(
                    vocabulary=vocabulary,
                    name=name,
                    slug=slug,
                    parent=parent,
                    description=description,
                    is_active=is_active,
                    metadata=metadata,
                )
                imported_terms[slug] = term
                created += 1

        # --- Step 4: Import relationships (idempotent via add_relationship) ---
        for rel_data in data.get("relationships", []):
            from_slug = rel_data.get("term_from_slug")
            to_slug = rel_data.get("term_to_slug")
            rel_type = rel_data.get("relationship_type")

            term_from = imported_terms.get(from_slug)
            term_to = imported_terms.get(to_slug)

            if term_from is None or term_to is None:
                # One or both terms were not imported; skip this relationship.
                continue

            try:
                add_relationship(term_from, term_to, rel_type)
            except TaxonomyValidationError:
                # Self-relationship or other validation error — skip.
                pass

    return {"created": created, "updated": updated, "skipped": skipped}
