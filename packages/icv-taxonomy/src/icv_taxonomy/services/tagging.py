"""Tagging services for icv-taxonomy.

Handles association of terms with arbitrary Django model instances via
the TermAssociation generic FK model, plus helpers for querying tagged
objects and typed M2M through tables.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from ..exceptions import TaxonomyValidationError

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_association_model() -> type:
    """Return the TermAssociation model, resolved at call time.

    Returns:
        The TermAssociation model class.
    """
    from django.apps import apps

    return apps.get_model("icv_taxonomy", "TermAssociation")


def _str_pk(obj: Any) -> str:
    """Return the PK of a model instance as a string.

    Args:
        obj: A Django model instance.

    Returns:
        str representation of obj.pk.
    """
    return str(obj.pk)


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def tag_object(term: Any, obj: Any) -> Any:
    """Associate a term with a model instance.

    Validates that the term is active (BR-TAX-017) and that the association
    is unique (BR-TAX-015). For vocabularies with ``allow_multiple=False``,
    also validates cardinality (BR-TAX-016). The ``order`` field is set to
    ``max(order)+1`` for existing associations on this object, or 0 if this
    is the first (BR-TAX-019).

    Args:
        term: The Term to apply as a tag. Must have ``is_active=True``.
        obj: The Django model instance to tag.

    Returns:
        The newly created TermAssociation instance.

    Raises:
        TaxonomyValidationError: If the term is inactive, the association
            already exists, or the vocabulary's cardinality is exceeded.

    Side effects:
        Inserts a TermAssociation row.
        Emits ``object_tagged`` signal.
    """
    from ..signals import object_tagged

    # BR-TAX-017: Active terms only.
    if not term.is_active:
        raise TaxonomyValidationError(f"Term '{term.slug}' is inactive and cannot be used for tagging (BR-TAX-017).")

    TermAssociation = _get_association_model()
    ct = ContentType.objects.get_for_model(obj)
    object_id = _str_pk(obj)

    # BR-TAX-015: Uniqueness check (guard before the DB constraint fires).
    if TermAssociation.objects.filter(term=term, content_type=ct, object_id=object_id).exists():
        raise TaxonomyValidationError(f"Term '{term.slug}' is already associated with this object (BR-TAX-015).")

    # BR-TAX-016: Cardinality check for single-term vocabularies.
    if not term.vocabulary.allow_multiple:
        existing_count = TermAssociation.objects.filter(
            content_type=ct,
            object_id=object_id,
            term__vocabulary=term.vocabulary,
        ).count()
        if existing_count >= 1:
            raise TaxonomyValidationError(
                f"Vocabulary '{term.vocabulary.slug}' does not allow multiple terms per object (BR-TAX-016)."
            )

    # BR-TAX-019: Order defaults to append.
    from django.db.models import Max

    max_order = TermAssociation.objects.filter(content_type=ct, object_id=object_id).aggregate(Max("order"))[
        "order__max"
    ]
    next_order = (max_order + 1) if max_order is not None else 0

    association = TermAssociation.objects.create(
        term=term,
        content_type=ct,
        object_id=object_id,
        order=next_order,
    )

    object_tagged.send(
        sender=term.__class__,
        term=term,
        content_object=obj,
        content_type=ct,
        object_id=object_id,
    )

    return association


def untag_object(term: Any, obj: Any) -> None:
    """Remove the association between a term and a model instance.

    Emits ``object_untagged`` before deletion so handlers can still read
    the association.

    Args:
        term: The Term to remove.
        obj: The Django model instance to untag.

    Returns:
        None

    Raises:
        TaxonomyValidationError: If no association exists between the term
            and the object.

    Side effects:
        Deletes the TermAssociation row.
        Emits ``object_untagged`` signal.
    """
    from ..signals import object_untagged

    TermAssociation = _get_association_model()
    ct = ContentType.objects.get_for_model(obj)
    object_id = _str_pk(obj)

    try:
        association = TermAssociation.objects.get(term=term, content_type=ct, object_id=object_id)
    except TermAssociation.DoesNotExist as exc:
        raise TaxonomyValidationError(f"No association exists between term '{term.slug}' and this object.") from exc

    object_untagged.send(
        sender=term.__class__,
        term=term,
        content_object=obj,
        content_type=ct,
        object_id=object_id,
    )

    association.delete()


def get_terms_for_object(
    obj: Any,
    vocabulary: Any | None = None,
    vocabulary_slug: str | None = None,
) -> Any:
    """Return the terms associated with a model instance.

    Args:
        obj: The Django model instance to query.
        vocabulary: Optional Vocabulary instance to restrict results to.
        vocabulary_slug: Optional vocabulary slug to restrict results to.
            Ignored if ``vocabulary`` is provided.

    Returns:
        A QuerySet of Term instances ordered by association order and
        creation time. Uses ``select_related("vocabulary")`` to avoid N+1
        queries when accessing vocabulary attributes.

    Side effects:
        None (pure read).
    """
    from ..conf import get_term_model

    TermAssociation = _get_association_model()
    Term = get_term_model()

    ct = ContentType.objects.get_for_model(obj)
    object_id = _str_pk(obj)

    assoc_qs = TermAssociation.objects.filter(content_type=ct, object_id=object_id).order_by("order", "created_at")

    term_ids = assoc_qs.values_list("term_id", flat=True)
    qs = Term.all_objects.filter(pk__in=term_ids).select_related("vocabulary")

    if vocabulary is not None:
        qs = qs.filter(vocabulary=vocabulary)
    elif vocabulary_slug is not None:
        qs = qs.filter(vocabulary__slug=vocabulary_slug)

    return qs


def get_objects_for_term(
    term: Any,
    model_class: type | None = None,
) -> Any:
    """Return the objects tagged with a given term.

    Args:
        term: The Term to query associations for.
        model_class: Optional concrete model class. When provided, returns a
            typed QuerySet for that model. When None, resolves all
            associations via GenericForeignKey and returns a list of model
            instances (heterogeneous types possible).

    Returns:
        A typed QuerySet if ``model_class`` is provided, otherwise a list of
        content objects (resolved via GenericFK).

    Side effects:
        None (pure read).
    """
    TermAssociation = _get_association_model()
    assocs = TermAssociation.objects.filter(term=term)

    if model_class is not None:
        ct = ContentType.objects.get_for_model(model_class)
        # object_id is stored as CharField(255); cast values to the concrete
        # PK type of the model before passing to pk__in so PostgreSQL does
        # not reject the bigint = varchar comparison.
        pk_field = model_class._meta.pk
        raw_ids = list(assocs.filter(content_type=ct).values_list("object_id", flat=True))
        try:
            typed_ids = [pk_field.to_python(oid) for oid in raw_ids]
        except Exception:  # noqa: BLE001
            typed_ids = raw_ids
        return model_class.objects.filter(pk__in=typed_ids)

    # Heterogeneous list — resolve GenericFK.
    # select_related("content_type") avoids N+1 queries for content type lookups.
    assocs = assocs.select_related("content_type")
    return [a.content_object for a in assocs if a.content_object is not None]


def replace_term_on_object(obj: Any, old_term: Any, new_term: Any) -> Any:
    """Replace one term tag with another on a model instance.

    Wraps ``untag_object`` and ``tag_object`` in a single atomic transaction.
    Cardinality validation is handled by ``tag_object``.

    Args:
        obj: The Django model instance to update.
        old_term: The Term to remove.
        new_term: The Term to apply in its place.

    Returns:
        The newly created TermAssociation for new_term.

    Raises:
        TaxonomyValidationError: If old_term is not currently associated with
            obj, or if tag_object validation fails for new_term.

    Side effects:
        Deletes the old TermAssociation; inserts a new one.
        Emits ``object_untagged`` then ``object_tagged``.
    """
    with transaction.atomic():
        untag_object(old_term, obj)
        return tag_object(new_term, obj)


def bulk_tag_objects(
    term: Any,
    objects: list[Any],
    emit_signals: bool = True,
) -> list[Any]:
    """Tag multiple objects with a term in bulk.

    Uses ``bulk_create`` with ``ignore_conflicts=True`` to skip duplicates
    without raising. When ``emit_signals=True``, emits ``object_tagged`` for
    each newly created association. When ``False``, signals are suppressed for
    performance — the caller is responsible for downstream updates (e.g.,
    search re-indexing).

    Args:
        term: The Term to apply to all objects. Must be active.
        objects: A list of Django model instances to tag.
        emit_signals: Whether to emit ``object_tagged`` for each new
            association. Defaults to True.

    Returns:
        A list of TermAssociation instances that were actually inserted
        (duplicates excluded).

    Raises:
        TaxonomyValidationError: If the term is inactive.

    Side effects:
        Bulk-inserts TermAssociation rows; skips duplicates.
        Emits ``object_tagged`` per new association when emit_signals=True.
    """
    from ..signals import object_tagged

    if not term.is_active:
        raise TaxonomyValidationError(f"Term '{term.slug}' is inactive and cannot be used for tagging (BR-TAX-017).")

    TermAssociation = _get_association_model()

    to_create = []
    ct_cache: dict[type, ContentType] = {}

    for obj in objects:
        obj_type = type(obj)
        if obj_type not in ct_cache:
            ct_cache[obj_type] = ContentType.objects.get_for_model(obj)
        ct = ct_cache[obj_type]
        object_id = _str_pk(obj)
        to_create.append(
            TermAssociation(
                term=term,
                content_type=ct,
                object_id=object_id,
                order=0,
            )
        )

    # bulk_create returns only the rows that were actually inserted on
    # backends that support it (PostgreSQL). On others (SQLite), it may
    # return an empty list when ignore_conflicts=True.
    created = TermAssociation.objects.bulk_create(to_create, ignore_conflicts=True)

    if emit_signals and created:
        for assoc in created:
            object_tagged.send(
                sender=term.__class__,
                term=term,
                content_object=assoc.content_object,
                content_type=assoc.content_type,
                object_id=assoc.object_id,
            )

    return created


def get_terms_for_object_typed(
    obj: Any,
    through_model: type | None,
    vocabulary: Any | None = None,
) -> Any:
    """Return terms for an object via a typed M2M through table.

    For high-volume use cases where the generic ``TermAssociation`` FK
    overhead is unacceptable. Queries the typed M2M through table generated
    by ``create_term_m2m()`` using direct FK joins — no GenericFK resolution.

    Falls back to ``get_terms_for_object()`` if ``through_model`` is None.

    Args:
        obj: The Django model instance to query.
        through_model: The concrete M2M through model generated by
            ``create_term_m2m()``.
        vocabulary: Optional Vocabulary to restrict results to.

    Returns:
        A QuerySet of Term instances joined via the typed through table.

    Side effects:
        None (pure read).
    """
    if through_model is None:
        return get_terms_for_object(obj, vocabulary=vocabulary)

    from ..conf import get_term_model

    Term = get_term_model()

    # Discover the FK field name on the through model that points at obj's model.
    obj_model = type(obj)
    fk_field_name: str | None = None
    for field in through_model._meta.get_fields():
        if hasattr(field, "related_model") and field.related_model is obj_model and hasattr(field, "attname"):
            fk_field_name = field.name
            break

    if fk_field_name is None:
        raise TaxonomyValidationError(
            f"through_model '{through_model.__name__}' has no FK pointing to '{obj_model.__name__}'."
        )

    term_ids = through_model.objects.filter(**{fk_field_name: obj}).values_list("term_id", flat=True)

    qs = Term.all_objects.filter(pk__in=term_ids).select_related("vocabulary")

    if vocabulary is not None:
        qs = qs.filter(vocabulary=vocabulary)

    return qs


def cleanup_orphaned_associations(
    model_class: type | None = None,
    dry_run: bool = False,
) -> dict:
    """Detect and remove TermAssociation rows whose objects no longer exist.

    Generic FK associations have no database-level cascade — when a tagged
    object is deleted, the TermAssociation row persists as an orphan
    (BR-TAX-018). This function detects and removes them.

    Args:
        model_class: Optional model class to restrict the cleanup to a single
            content type. When None, all content types with associations are
            checked.
        dry_run: When True, reports counts without deleting anything.

    Returns:
        A dict with cleanup statistics::

            {"checked": int, "orphaned": int, "removed": int}

    Side effects:
        Deletes orphaned TermAssociation rows unless ``dry_run=True``.
    """
    TermAssociation = _get_association_model()

    checked = 0
    orphaned = 0
    removed = 0

    if model_class is not None:
        ct = ContentType.objects.get_for_model(model_class)
        content_types_to_check = [ct]
    else:
        content_types_to_check = list(
            ContentType.objects.filter(
                pk__in=TermAssociation.objects.values_list("content_type_id", flat=True).distinct()
            )
        )

    for ct in content_types_to_check:
        model_cls = ct.model_class()
        if model_cls is None:
            # Model has been removed from the codebase; all these assocs are orphaned.
            assoc_qs = TermAssociation.objects.filter(content_type=ct)
            count = assoc_qs.count()
            checked += count
            orphaned += count
            if not dry_run:
                assoc_qs.delete()
                removed += count
            continue

        existing_ids = set(model_cls.objects.values_list("pk", flat=True))
        assocs_for_type = TermAssociation.objects.filter(content_type=ct)
        checked += assocs_for_type.count()

        # Collect orphaned object_ids.
        orphaned_object_ids = [
            oid
            for oid in assocs_for_type.values_list("object_id", flat=True).distinct()
            if str(oid) not in {str(pk) for pk in existing_ids}
        ]

        if orphaned_object_ids:
            orphaned_qs = TermAssociation.objects.filter(content_type=ct, object_id__in=orphaned_object_ids)
            count = orphaned_qs.count()
            orphaned += count
            if not dry_run:
                orphaned_qs.delete()
                removed += count

    return {"checked": checked, "orphaned": orphaned, "removed": removed}
