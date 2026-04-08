"""Term lifecycle services for icv-taxonomy.

Handles creation, update, move, merge, deletion, and deactivation of Term
instances. All business rules from BR-TAX-007 through BR-TAX-014 and
BR-TAX-024 through BR-TAX-029, BR-TAX-042 are enforced here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils.text import slugify

from ..exceptions import TaxonomyValidationError

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_term_slug(name: str, base_slug: str, vocabulary: Any, model_cls: type) -> str:
    """Return a slug unique within the vocabulary.

    Args:
        name: Term name used as slug source when base_slug is blank.
        base_slug: Caller-supplied slug; derived from name if blank.
        vocabulary: The Vocabulary instance the term belongs to.
        model_cls: The concrete Term model class.

    Returns:
        A slug not already used by another term in the same vocabulary.

    Side effects:
        Read-only DB query.
    """
    from ..conf import get_setting

    slug_max = get_setting("ICV_TAXONOMY_SLUG_MAX_LENGTH", 255)
    case_sensitive = get_setting("ICV_TAXONOMY_CASE_SENSITIVE_SLUGS", False)

    candidate = base_slug or slugify(name)
    if not case_sensitive:
        candidate = candidate.lower()
    candidate = candidate[:slug_max]

    if not model_cls.all_objects.filter(vocabulary=vocabulary, slug=candidate).exists():
        return candidate

    counter = 2
    while True:
        suffix = f"-{counter}"
        truncated = candidate[: slug_max - len(suffix)]
        numbered = truncated + suffix
        if not model_cls.all_objects.filter(vocabulary=vocabulary, slug=numbered).exists():
            return numbered
        counter += 1


def _validate_create_term(
    vocabulary: Any,
    parent: Any | None,
    term_model: type,
) -> None:
    """Run pre-creation validation checks for a new term.

    Args:
        vocabulary: The target Vocabulary instance.
        parent: The intended parent Term, or None for a root term.
        term_model: The concrete Term model class.

    Returns:
        None

    Raises:
        TaxonomyValidationError: If any business rule is violated.
    """
    from ..conf import get_setting

    # BR-TAX-003: Closed vocabulary rejects new terms.
    if not vocabulary.is_open:
        raise TaxonomyValidationError(
            f"Vocabulary '{vocabulary.slug}' is closed and does not accept new terms (BR-TAX-003)."
        )

    # BR-TAX-008: Flat vocabulary terms must have no parent.
    enforce = get_setting("ICV_TAXONOMY_ENFORCE_VOCABULARY_TYPE", True)
    if enforce and vocabulary.vocabulary_type == "flat" and parent is not None:
        raise TaxonomyValidationError(
            f"Vocabulary '{vocabulary.slug}' is flat; terms must not have a parent (BR-TAX-008)."
        )

    # BR-TAX-014: Parent must be in the same vocabulary.
    if parent is not None and parent.vocabulary_id != vocabulary.pk:
        raise TaxonomyValidationError("Parent term must belong to the same vocabulary as the new term (BR-TAX-014).")

    # BR-TAX-009: Term depth must respect max_depth.
    if parent is not None and vocabulary.max_depth is not None:
        proposed_depth = parent.depth + 1
        if proposed_depth > vocabulary.max_depth:
            raise TaxonomyValidationError(
                f"Cannot create term at depth {proposed_depth}; vocabulary "
                f"'{vocabulary.slug}' max_depth is {vocabulary.max_depth} (BR-TAX-009)."
            )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def create_term(
    vocabulary: Any,
    name: str,
    slug: str = "",
    parent: Any | None = None,
    **kwargs: Any,
) -> Any:
    """Create and persist a new Term within a vocabulary.

    Validates closed vocabulary (BR-TAX-003), flat constraint (BR-TAX-008),
    max depth (BR-TAX-009), and vocabulary boundary (BR-TAX-014).
    Auto-generates slug with collision resolution (BR-TAX-007).
    The ``term_created`` signal is emitted by the post-save handler.

    Args:
        vocabulary: The Vocabulary instance to add the term to.
        name: Human-readable term name (e.g., "Red").
        slug: URL-safe identifier. Auto-generated from name if blank.
        parent: Parent Term for hierarchical vocabularies. Must be None for
            flat vocabularies.
        **kwargs: Additional field values (e.g., ``description``, ``metadata``,
            ``is_active``).

    Returns:
        The newly created Term instance.

    Raises:
        TaxonomyValidationError: If business-rule validation fails.

    Side effects:
        Inserts a row into the term table.
        Emits ``term_created`` via post-save handler.
    """
    from ..conf import get_term_model

    Term = get_term_model()

    _validate_create_term(vocabulary, parent, Term)

    resolved_slug = _resolve_term_slug(name, slug, vocabulary, Term)

    term = Term(
        vocabulary=vocabulary,
        name=name,
        slug=resolved_slug,
        parent=parent,
        **kwargs,
    )
    term.full_clean()
    term.save()
    return term


def update_term(term: Any, **kwargs: Any) -> Any:
    """Update mutable fields on an existing Term instance.

    Validates that ``vocabulary`` is not changed after creation (BR-TAX-010).

    Args:
        term: The Term instance to update.
        **kwargs: Field name → new value pairs. Only provided fields are
            updated.

    Returns:
        The updated Term instance.

    Raises:
        TaxonomyValidationError: If attempting to change the term's vocabulary.

    Side effects:
        Updates the term row in the database.
    """
    if "vocabulary" in kwargs and kwargs["vocabulary"] != term.vocabulary:
        raise TaxonomyValidationError("A term's vocabulary cannot be changed after creation (BR-TAX-010).")

    for field, value in kwargs.items():
        setattr(term, field, value)

    update_fields = list(kwargs.keys())
    if update_fields:
        term.full_clean()
        term.save(update_fields=update_fields)
    return term


def move_term(
    term: Any,
    target: Any,
    position: str = "last-child",
) -> None:
    """Move a term (and its subtree) to a new position within the same vocabulary.

    Delegates to ``icv_tree.services.move_to()``. The ``term_moved`` signal is
    emitted by the ``handlers._handle_node_moved`` bridge which listens to
    icv-tree's ``node_moved`` signal.

    Args:
        term: The Term to move.
        target: Reference Term. Interpretation depends on ``position``.
        position: One of ``"first-child"``, ``"last-child"``, ``"left"``,
            ``"right"``. Defaults to ``"last-child"``.

    Returns:
        None

    Raises:
        TaxonomyValidationError: If target is in a different vocabulary.
        icv_tree.exceptions.TreeStructureError: If the move would create a
            cycle or uses an invalid position value.

    Side effects:
        Updates path, depth, and order on the moved node and all descendants.
        Emits ``term_moved`` via the node_moved → term_moved bridge handler.
    """
    if term.vocabulary_id != target.vocabulary_id:
        raise TaxonomyValidationError(
            "Cannot move a term to a position under a target from a different vocabulary (BR-TAX-014)."
        )

    from icv_tree.services import move_to

    move_to(term, target, position)


def merge_terms(
    source: Any,
    target: Any,
    children_strategy: str = "refuse",
) -> dict:
    """Merge source term into target, transferring associations and relationships.

    Validates same vocabulary (BR-TAX-029), validates children_strategy
    (BR-TAX-042), transfers associations (BR-TAX-024), transfers relationships
    (BR-TAX-025), re-parents children if specified, deactivates source
    (BR-TAX-026), emits ``term_merged`` (BR-TAX-027). Wrapped in
    ``transaction.atomic`` (BR-TAX-028).

    Args:
        source: The Term to merge from. Will be deactivated after the merge.
        target: The Term to merge into. Receives all transferred records.
        children_strategy: How to handle source's children. One of:

            - ``"refuse"`` (default) — raise if source has children.
            - ``"reparent"`` — re-parent children to target.
            - ``"reparent_up"`` — re-parent children to source's parent (or
              make them roots if source is a root term).

    Returns:
        A dict with counts::

            {
                "associations_transferred": int,
                "relationships_transferred": int,
                "children_reparented": int,
            }

    Raises:
        TaxonomyValidationError: If source and target are in different
            vocabularies (BR-TAX-029), if ``children_strategy`` is invalid
            (BR-TAX-042), or if ``children_strategy="refuse"`` and source
            has children.

    Side effects:
        Reassigns TermAssociation rows from source to target (skips duplicates).
        Reassigns TermRelationship rows involving source to target (skips
        duplicates).
        Re-parents child terms if strategy demands it.
        Sets ``source.is_active = False``.
        Emits ``term_merged`` signal on commit.
    """
    from ..conf import get_term_model
    from ..signals import term_merged

    _VALID_STRATEGIES = {"refuse", "reparent", "reparent_up"}

    # Validation — must happen before the atomic block so that errors
    # surface cleanly without wrapping DB-level rollback behaviour.
    if children_strategy not in _VALID_STRATEGIES:
        raise TaxonomyValidationError(
            f"Invalid children_strategy '{children_strategy}'. "
            f"Must be one of: {', '.join(sorted(_VALID_STRATEGIES))} (BR-TAX-042)."
        )

    if source.vocabulary_id != target.vocabulary_id:
        raise TaxonomyValidationError("source and target must belong to the same vocabulary (BR-TAX-029).")

    Term = get_term_model()
    children = list(Term.all_objects.filter(parent=source))

    if children and children_strategy == "refuse":
        raise TaxonomyValidationError(
            f"Term '{source.slug}' has {len(children)} child term(s). Specify "
            "children_strategy='reparent' or 'reparent_up' to proceed (BR-TAX-042)."
        )

    associations_transferred = 0
    relationships_transferred = 0
    children_reparented = 0

    # Lazily import the association and relationship models to avoid circular
    # imports at module level.
    def _get_association_model():
        from django.apps import apps

        return apps.get_model("icv_taxonomy", "TermAssociation")

    def _get_relationship_model():
        from django.apps import apps

        return apps.get_model("icv_taxonomy", "TermRelationship")

    with transaction.atomic():
        TermAssociation = _get_association_model()
        TermRelationship = _get_relationship_model()

        # --- Step 1: Re-parent children (bulk) ---
        if children:
            new_parent = target if children_strategy == "reparent" else source.parent
            children_reparented = len(children)

            for child in children:
                child.parent = new_parent
            Term.objects.bulk_update(children, ["parent"])

        # --- Step 2: Transfer associations (BR-TAX-024) ---
        # Batch: find which source associations would be duplicates on target,
        # delete those, and bulk-reassign the rest.
        source_assocs = TermAssociation.objects.filter(term=source)

        # Identify duplicates in one query: source assocs whose (ct, oid)
        # already exists on target.
        existing_on_target = set(
            TermAssociation.objects.filter(term=target).values_list("content_type_id", "object_id")
        )

        duplicate_ids = []
        transfer_ids = []
        for assoc in source_assocs.values_list("pk", "content_type_id", "object_id"):
            pk, ct_id, oid = assoc
            if (ct_id, oid) in existing_on_target:
                duplicate_ids.append(pk)
            else:
                transfer_ids.append(pk)

        # Delete duplicates in bulk.
        if duplicate_ids:
            TermAssociation.objects.filter(pk__in=duplicate_ids).delete()

        # Transfer remaining in bulk.
        associations_transferred = TermAssociation.objects.filter(pk__in=transfer_ids).update(term=target)

        # --- Step 3: Transfer relationships (BR-TAX-025) ---
        # Handle term_from side — batch approach.
        from_rels = list(
            TermRelationship.objects.filter(term_from=source).values_list("pk", "term_to_id", "relationship_type")
        )

        # Self-loops (source→target becomes target→target) must be deleted.
        from_selfloop_ids = [pk for pk, to_id, _ in from_rels if to_id == target.pk]

        # Find existing (target, term_to, type) combos to detect duplicates.
        existing_from_target = set(
            TermRelationship.objects.filter(term_from=target).values_list("term_to_id", "relationship_type")
        )

        from_dup_ids = []
        from_transfer_ids = []
        for pk, to_id, rel_type in from_rels:
            if to_id == target.pk:
                continue  # already in selfloop list
            if (to_id, rel_type) in existing_from_target:
                from_dup_ids.append(pk)
            else:
                from_transfer_ids.append(pk)

        # Handle term_to side — same batch approach.
        to_rels = list(
            TermRelationship.objects.filter(term_to=source).values_list("pk", "term_from_id", "relationship_type")
        )

        to_selfloop_ids = [pk for pk, from_id, _ in to_rels if from_id == target.pk]

        existing_to_target = set(
            TermRelationship.objects.filter(term_to=target).values_list("term_from_id", "relationship_type")
        )

        to_dup_ids = []
        to_transfer_ids = []
        for pk, from_id, rel_type in to_rels:
            if from_id == target.pk:
                continue
            if (from_id, rel_type) in existing_to_target:
                to_dup_ids.append(pk)
            else:
                to_transfer_ids.append(pk)

        # Execute bulk deletes and updates.
        delete_ids = from_selfloop_ids + from_dup_ids + to_selfloop_ids + to_dup_ids
        if delete_ids:
            TermRelationship.objects.filter(pk__in=delete_ids).delete()

        from_transferred = TermRelationship.objects.filter(pk__in=from_transfer_ids).update(term_from=target)

        to_transferred = TermRelationship.objects.filter(pk__in=to_transfer_ids).update(term_to=target)

        relationships_transferred = from_transferred + to_transferred

        # --- Step 4: Deactivate source (BR-TAX-026) ---
        source.is_active = False
        source.save(update_fields=["is_active"])

        # Capture counts for signal emission after commit.
        _assocs = associations_transferred
        _children = children_reparented

    # Emit signal after the transaction commits (BR-TAX-027).
    def _emit() -> None:
        term_merged.send(
            sender=source.__class__,
            source=source,
            target=target,
            associations_transferred=_assocs,
            children_reparented=_children,
        )

    transaction.on_commit(_emit)

    return {
        "associations_transferred": associations_transferred,
        "relationships_transferred": relationships_transferred,
        "children_reparented": children_reparented,
    }


def delete_term(term: Any) -> None:
    """Hard-delete a term and all its cascaded descendants.

    The ``term_deleted`` signal is emitted by the pre-delete handler wired
    in ``handlers.py`` — the handler fires before the DELETE reaches the
    database so that downstream code can still read the term's associations.

    Args:
        term: The Term instance to delete.

    Returns:
        None

    Side effects:
        Deletes the term and all cascaded rows (children, associations,
        relationships).
        Emits ``term_deleted`` via pre-delete handler.
    """
    term.delete()


def deactivate_term(term: Any) -> Any:
    """Set ``is_active=False`` on a term without deleting it.

    Existing TermAssociation records are preserved (BR-TAX-013). Only new
    tagging operations are blocked for inactive terms.

    Args:
        term: The Term instance to deactivate.

    Returns:
        The updated Term instance.

    Side effects:
        Sets ``term.is_active = False`` and saves.
    """
    term.is_active = False
    term.save(update_fields=["is_active"])
    return term
