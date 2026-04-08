"""Tests for icv-taxonomy service functions.

Covers vocabulary_management, term_management, tagging, relationships,
and import_export services. Business rules referenced in docstrings refer
to the APP-021 spec (docs/specs/APP-021-taxonomy/02-business-rules.md).
"""

from __future__ import annotations

import pytest

# ===========================================================================
# vocabulary_management
# ===========================================================================


@pytest.mark.django_db
class TestCreateVocabulary:
    """Tests for create_vocabulary()."""

    def test_creates_vocabulary_with_explicit_slug(self):
        """Vocabulary is created with the caller-supplied slug."""
        from icv_taxonomy.services import create_vocabulary

        vocab = create_vocabulary(name="Colours", slug="colours")
        assert vocab.pk is not None
        assert vocab.slug == "colours"

    def test_auto_slug_from_name(self):
        """Slug is derived from name when slug is blank (BR-TAX-043)."""
        from icv_taxonomy.services import create_vocabulary

        vocab = create_vocabulary(name="My Vocabulary")
        assert vocab.slug == "my-vocabulary"

    def test_slug_collision_appends_suffix(self):
        """Second vocabulary with colliding slug gets -2 suffix (BR-TAX-043)."""
        from icv_taxonomy.services import create_vocabulary

        create_vocabulary(name="Tags", slug="tags")
        vocab2 = create_vocabulary(name="Tags Again", slug="tags")
        assert vocab2.slug == "tags-2"

    def test_slug_lowercased_by_default(self, settings):
        """Slug is lowercased when ICV_TAXONOMY_CASE_SENSITIVE_SLUGS=False (BR-TAX-034)."""
        settings.ICV_TAXONOMY_CASE_SENSITIVE_SLUGS = False
        from icv_taxonomy.services import create_vocabulary

        vocab = create_vocabulary(name="Upper Case")
        assert vocab.slug == vocab.slug.lower()

    def test_default_vocabulary_type_is_flat(self):
        """Vocabulary defaults to flat type."""
        from icv_taxonomy.services import create_vocabulary

        vocab = create_vocabulary(name="Simple Tags")
        assert vocab.vocabulary_type == "flat"

    def test_creates_hierarchical_vocabulary(self):
        """Hierarchical vocabulary type is accepted."""
        from icv_taxonomy.services import create_vocabulary

        vocab = create_vocabulary(name="Topics", vocabulary_type="hierarchical")
        assert vocab.vocabulary_type == "hierarchical"


@pytest.mark.django_db
class TestUpdateVocabulary:
    """Tests for update_vocabulary()."""

    def test_updates_name(self, flat_vocabulary):
        """Name can be updated on an existing vocabulary."""
        from icv_taxonomy.services import update_vocabulary

        updated = update_vocabulary(flat_vocabulary, name="New Name")
        flat_vocabulary.refresh_from_db()
        assert updated.name == "New Name"
        assert flat_vocabulary.name == "New Name"

    def test_raises_on_type_change_with_terms(self, flat_vocabulary):
        """Changing vocabulary_type when terms exist raises TaxonomyValidationError (BR-TAX-002)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import update_vocabulary

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-002"):
            update_vocabulary(flat_vocabulary, vocabulary_type="hierarchical")

    def test_type_change_allowed_on_empty_vocabulary(self, db):
        """vocabulary_type can be changed when no terms exist."""
        from icv_taxonomy.services import create_vocabulary, update_vocabulary

        vocab = create_vocabulary(name="Empty", vocabulary_type="flat")
        updated = update_vocabulary(vocab, vocabulary_type="hierarchical")
        assert updated.vocabulary_type == "hierarchical"


@pytest.mark.django_db
class TestDeleteVocabulary:
    """Tests for delete_vocabulary()."""

    def test_deletes_vocabulary(self, db):
        """Vocabulary row is removed from the database."""
        from icv_taxonomy.models import Vocabulary
        from icv_taxonomy.services import create_vocabulary, delete_vocabulary

        vocab = create_vocabulary(name="Temporary")
        vocab_pk = vocab.pk
        delete_vocabulary(vocab)
        assert not Vocabulary.all_objects.filter(pk=vocab_pk).exists()

    def test_cascades_to_terms(self, flat_vocabulary):
        """Deleting vocabulary also deletes its terms (BR-TAX-004)."""
        from icv_taxonomy.models import Term

        term_count_before = Term.all_objects.filter(vocabulary=flat_vocabulary).count()
        assert term_count_before > 0

        from icv_taxonomy.services import delete_vocabulary

        vocab_pk = flat_vocabulary.pk
        delete_vocabulary(flat_vocabulary)

        assert Term.all_objects.filter(vocabulary_id=vocab_pk).count() == 0


@pytest.mark.django_db
class TestClearVocabulary:
    """Tests for clear_vocabulary()."""

    def test_removes_all_terms(self, flat_vocabulary):
        """All terms in the vocabulary are deleted."""
        from icv_taxonomy.models import Term
        from icv_taxonomy.services import clear_vocabulary

        assert Term.all_objects.filter(vocabulary=flat_vocabulary).count() > 0
        clear_vocabulary(flat_vocabulary)
        assert Term.all_objects.filter(vocabulary=flat_vocabulary).count() == 0

    def test_preserves_vocabulary(self, flat_vocabulary):
        """The vocabulary itself is not deleted."""
        from icv_taxonomy.models import Vocabulary
        from icv_taxonomy.services import clear_vocabulary

        vocab_pk = flat_vocabulary.pk
        clear_vocabulary(flat_vocabulary)
        assert Vocabulary.all_objects.filter(pk=vocab_pk).exists()

    def test_returns_correct_count(self, flat_vocabulary):
        """Return value equals the number of terms that were deleted."""
        from icv_taxonomy.services import clear_vocabulary

        # flat_vocabulary fixture creates 5 terms.
        count = clear_vocabulary(flat_vocabulary)
        assert count == 5

    def test_returns_zero_on_empty_vocabulary(self, db):
        """Returns 0 when the vocabulary has no terms."""
        from icv_taxonomy.services import clear_vocabulary, create_vocabulary

        empty = create_vocabulary(name="Empty Vocab", vocabulary_type="flat")
        count = clear_vocabulary(empty)
        assert count == 0

    def test_cascades_to_term_associations(self, flat_vocabulary, article):
        """Clearing the vocabulary removes all TermAssociation rows for its terms."""
        from django.apps import apps

        from icv_taxonomy.services import clear_vocabulary, tag_object

        term = flat_vocabulary.terms.first()
        tag_object(term, article)

        TermAssociation = apps.get_model("icv_taxonomy", "TermAssociation")
        assert TermAssociation.objects.filter(term=term).count() == 1

        clear_vocabulary(flat_vocabulary)
        assert TermAssociation.objects.filter(term=term).count() == 0

    def test_cascades_to_term_relationships(self, flat_vocabulary):
        """Clearing the vocabulary removes all TermRelationship rows for its terms."""
        from django.apps import apps

        from icv_taxonomy.services import add_relationship, clear_vocabulary

        terms = list(flat_vocabulary.terms.all()[:2])
        add_relationship(terms[0], terms[1], "related")

        TermRelationship = apps.get_model("icv_taxonomy", "TermRelationship")
        assert TermRelationship.objects.filter(term_from=terms[0]).count() == 1

        clear_vocabulary(flat_vocabulary)
        assert TermRelationship.objects.filter(term_from=terms[0]).count() == 0

    def test_includes_inactive_terms(self, flat_vocabulary):
        """Inactive terms are also deleted (all_objects manager is used)."""
        from icv_taxonomy.models import Term
        from icv_taxonomy.services import clear_vocabulary, deactivate_term

        first_term = flat_vocabulary.terms.first()
        deactivate_term(first_term)

        # Confirm at least one term is inactive.
        assert Term.all_objects.filter(vocabulary=flat_vocabulary, is_active=False).exists()

        count = clear_vocabulary(flat_vocabulary)
        assert count == 5
        assert Term.all_objects.filter(vocabulary=flat_vocabulary).count() == 0


# ===========================================================================
# term_management
# ===========================================================================


@pytest.mark.django_db
class TestCreateTerm:
    """Tests for create_term()."""

    def test_creates_root_term_in_flat_vocabulary(self, db):
        """A root term is created in a flat vocabulary."""
        from icv_taxonomy.services import create_term, create_vocabulary

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Python")
        assert term.pk is not None
        assert term.name == "Python"
        assert term.parent is None

    def test_auto_slug_from_name(self, db):
        """Term slug is auto-generated from name when blank (BR-TAX-007)."""
        from icv_taxonomy.services import create_term, create_vocabulary

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Machine Learning")
        assert term.slug == "machine-learning"

    def test_slug_collision_resolution(self, db):
        """Term with colliding slug gets -2 suffix (BR-TAX-007)."""
        from icv_taxonomy.services import create_term, create_vocabulary

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        create_term(vocabulary=vocab, name="Python", slug="python")
        term2 = create_term(vocabulary=vocab, name="Python Again", slug="python")
        assert term2.slug == "python-2"

    def test_raises_on_closed_vocabulary(self, closed_vocabulary):
        """Adding term to closed vocabulary raises TaxonomyValidationError (BR-TAX-003)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import create_term

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-003"):
            create_term(vocabulary=closed_vocabulary, name="New Term")

    def test_raises_on_flat_vocabulary_with_parent(self, db):
        """Creating a term with a parent in a flat vocabulary raises (BR-TAX-008)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import create_term, create_vocabulary

        vocab = create_vocabulary(name="Flat", vocabulary_type="flat")
        root = create_term(vocabulary=vocab, name="Root")

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-008"):
            create_term(vocabulary=vocab, name="Child", parent=root)

    def test_creates_hierarchical_term_with_parent(self, db):
        """Term with parent is created in a hierarchical vocabulary."""
        from icv_taxonomy.services import create_term, create_vocabulary

        vocab = create_vocabulary(name="Topics", vocabulary_type="hierarchical")
        root = create_term(vocabulary=vocab, name="Science")
        child = create_term(vocabulary=vocab, name="Physics", parent=root)
        assert child.parent_id == root.pk

    def test_raises_on_max_depth_exceeded(self, db):
        """Term exceeding max_depth raises TaxonomyValidationError (BR-TAX-009)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import create_term, create_vocabulary

        vocab = create_vocabulary(name="Shallow", vocabulary_type="hierarchical", max_depth=1)
        root = create_term(vocabulary=vocab, name="Root")
        child = create_term(vocabulary=vocab, name="Child", parent=root)

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-009"):
            create_term(vocabulary=vocab, name="Grandchild", parent=child)

    def test_raises_on_cross_vocabulary_parent(self, db):
        """Parent from a different vocabulary raises TaxonomyValidationError (BR-TAX-014)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import create_term, create_vocabulary

        vocab_a = create_vocabulary(name="A", vocabulary_type="hierarchical")
        vocab_b = create_vocabulary(name="B", vocabulary_type="hierarchical")
        root_a = create_term(vocabulary=vocab_a, name="Root A")

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-014"):
            create_term(vocabulary=vocab_b, name="Child B", parent=root_a)


@pytest.mark.django_db
class TestUpdateTerm:
    """Tests for update_term()."""

    def test_updates_name(self, db):
        """Term name is updated in place."""
        from icv_taxonomy.services import create_term, create_vocabulary, update_term

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Old Name")
        updated = update_term(term, name="New Name")
        term.refresh_from_db()
        assert updated.name == "New Name"
        assert term.name == "New Name"

    def test_raises_on_vocabulary_change(self, db):
        """Changing vocabulary raises TaxonomyValidationError (BR-TAX-010)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import create_term, create_vocabulary, update_term

        vocab_a = create_vocabulary(name="A", vocabulary_type="flat")
        vocab_b = create_vocabulary(name="B", vocabulary_type="flat")
        term = create_term(vocabulary=vocab_a, name="Term")

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-010"):
            update_term(term, vocabulary=vocab_b)


@pytest.mark.django_db
class TestMergeTerm:
    """Tests for merge_terms()."""

    def test_transfers_associations(self, db, article):
        """Associations on source are transferred to target (BR-TAX-024)."""
        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            get_terms_for_object,
            merge_terms,
            tag_object,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        source = create_term(vocabulary=vocab, name="Source")
        target = create_term(vocabulary=vocab, name="Target")
        tag_object(source, article)

        result = merge_terms(source, target)

        assert result["associations_transferred"] == 1
        terms = list(get_terms_for_object(article))
        assert len(terms) == 1
        assert terms[0].pk == target.pk

    def test_deactivates_source(self, db):
        """Source term is deactivated after merge (BR-TAX-026)."""
        from icv_taxonomy.services import create_term, create_vocabulary, merge_terms

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        source = create_term(vocabulary=vocab, name="Source")
        target = create_term(vocabulary=vocab, name="Target")
        merge_terms(source, target)

        source.refresh_from_db()
        assert source.is_active is False

    def test_raises_on_cross_vocabulary_merge(self, db):
        """Merging terms from different vocabularies raises (BR-TAX-029)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import create_term, create_vocabulary, merge_terms

        vocab_a = create_vocabulary(name="A", vocabulary_type="flat")
        vocab_b = create_vocabulary(name="B", vocabulary_type="flat")
        source = create_term(vocabulary=vocab_a, name="Source")
        target = create_term(vocabulary=vocab_b, name="Target")

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-029"):
            merge_terms(source, target)

    def test_raises_on_children_with_refuse_strategy(self, db):
        """merge_terms refuses if source has children and strategy is 'refuse' (BR-TAX-042)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import create_term, create_vocabulary, merge_terms

        vocab = create_vocabulary(name="Topics", vocabulary_type="hierarchical")
        source = create_term(vocabulary=vocab, name="Source")
        create_term(vocabulary=vocab, name="Child", parent=source)
        target = create_term(vocabulary=vocab, name="Target")

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-042"):
            merge_terms(source, target, children_strategy="refuse")

    def test_reparent_strategy_moves_children_to_target(self, db):
        """Reparent strategy moves source children to target (BR-TAX-042)."""
        from icv_taxonomy.services import create_term, create_vocabulary, merge_terms

        vocab = create_vocabulary(name="Topics", vocabulary_type="hierarchical")
        source = create_term(vocabulary=vocab, name="Source")
        child = create_term(vocabulary=vocab, name="Child", parent=source)
        target = create_term(vocabulary=vocab, name="Target")

        result = merge_terms(source, target, children_strategy="reparent")

        assert result["children_reparented"] == 1
        child.refresh_from_db()
        assert child.parent_id == target.pk

    def test_reparent_up_moves_children_to_sources_parent(self, db):
        """Reparent-up strategy moves source children to source's parent (BR-TAX-042)."""
        from icv_taxonomy.services import create_term, create_vocabulary, merge_terms

        vocab = create_vocabulary(name="Topics", vocabulary_type="hierarchical")
        grandparent = create_term(vocabulary=vocab, name="Grandparent")
        source = create_term(vocabulary=vocab, name="Source", parent=grandparent)
        child = create_term(vocabulary=vocab, name="Child", parent=source)
        target = create_term(vocabulary=vocab, name="Target", parent=grandparent)

        result = merge_terms(source, target, children_strategy="reparent_up")

        assert result["children_reparented"] == 1
        child.refresh_from_db()
        assert child.parent_id == grandparent.pk

    def test_skips_duplicate_associations(self, db, article):
        """Duplicate associations are silently skipped (BR-TAX-024)."""
        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            merge_terms,
            tag_object,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        source = create_term(vocabulary=vocab, name="Source")
        target = create_term(vocabulary=vocab, name="Target")
        # Tag the article with both source and target.
        tag_object(source, article)
        tag_object(target, article)

        result = merge_terms(source, target)
        # Source association is a duplicate — should be skipped not transferred.
        assert result["associations_transferred"] == 0

    def test_raises_on_invalid_children_strategy(self, db):
        """Invalid children_strategy raises TaxonomyValidationError."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import create_term, create_vocabulary, merge_terms

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        source = create_term(vocabulary=vocab, name="Source")
        target = create_term(vocabulary=vocab, name="Target")

        with pytest.raises(TaxonomyValidationError):
            merge_terms(source, target, children_strategy="invalid")


@pytest.mark.django_db
class TestDeactivateTerm:
    """Tests for deactivate_term()."""

    def test_sets_is_active_false(self, db):
        """deactivate_term() sets is_active=False without deleting."""
        from icv_taxonomy.services import create_term, create_vocabulary, deactivate_term

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Active Term")
        deactivate_term(term)

        term.refresh_from_db()
        assert term.is_active is False

    def test_preserves_associations_after_deactivation(self, db, article):
        """Deactivating a term does not remove its associations (BR-TAX-013)."""
        from django.apps import apps

        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            deactivate_term,
            tag_object,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Term")
        tag_object(term, article)
        deactivate_term(term)

        TermAssociation = apps.get_model("icv_taxonomy", "TermAssociation")
        assert TermAssociation.objects.filter(term=term).exists()


@pytest.mark.django_db
class TestDeleteTerm:
    """Tests for delete_term()."""

    def test_hard_deletes_term(self, db):
        """delete_term() removes the term row from the database."""
        from icv_taxonomy.models import Term
        from icv_taxonomy.services import create_term, create_vocabulary, delete_term

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Temp")
        pk = term.pk
        delete_term(term)
        assert not Term.all_objects.filter(pk=pk).exists()


# ===========================================================================
# tagging
# ===========================================================================


@pytest.mark.django_db
class TestTagObject:
    """Tests for tag_object()."""

    def test_creates_association(self, db, article):
        """tag_object() creates a TermAssociation row."""
        from django.apps import apps

        from icv_taxonomy.services import create_term, create_vocabulary, tag_object

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Python")
        assoc = tag_object(term, article)

        TermAssociation = apps.get_model("icv_taxonomy", "TermAssociation")
        assert assoc.pk is not None
        assert TermAssociation.objects.filter(pk=assoc.pk).exists()

    def test_raises_on_inactive_term(self, db, article):
        """Tagging with inactive term raises TaxonomyValidationError (BR-TAX-017)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            deactivate_term,
            tag_object,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Inactive")
        deactivate_term(term)

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-017"):
            tag_object(term, article)

    def test_raises_on_duplicate_association(self, db, article):
        """Tagging same object twice with same term raises (BR-TAX-015)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import create_term, create_vocabulary, tag_object

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Python")
        tag_object(term, article)

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-015"):
            tag_object(term, article)

    def test_raises_on_cardinality_violation(self, db, article):
        """Single-term vocab rejects second term (BR-TAX-016)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import create_term, create_vocabulary, tag_object

        vocab = create_vocabulary(name="Priority", vocabulary_type="flat", allow_multiple=False)
        term_a = create_term(vocabulary=vocab, name="High")
        term_b = create_term(vocabulary=vocab, name="Low")
        tag_object(term_a, article)

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-016"):
            tag_object(term_b, article)

    def test_order_appends_to_end(self, db, article):
        """Association order increments for subsequent tags (BR-TAX-019)."""
        from icv_taxonomy.services import create_term, create_vocabulary, tag_object

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A")
        term_b = create_term(vocabulary=vocab, name="B")
        assoc_a = tag_object(term_a, article)
        assoc_b = tag_object(term_b, article)

        assert assoc_b.order == assoc_a.order + 1

    def test_order_starts_at_zero_for_first_tag(self, db, article):
        """First association for an object has order=0 (BR-TAX-019)."""
        from icv_taxonomy.services import create_term, create_vocabulary, tag_object

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="First")
        assoc = tag_object(term, article)
        assert assoc.order == 0


@pytest.mark.django_db
class TestUntagObject:
    """Tests for untag_object()."""

    def test_removes_association(self, db, article):
        """untag_object() deletes the TermAssociation row."""
        from django.apps import apps

        from icv_taxonomy.services import create_term, create_vocabulary, tag_object, untag_object

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Python")
        tag_object(term, article)
        untag_object(term, article)

        TermAssociation = apps.get_model("icv_taxonomy", "TermAssociation")
        assert not TermAssociation.objects.filter(term=term).exists()

    def test_raises_if_not_tagged(self, db, article):
        """untag_object() raises if the term is not currently associated."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import create_term, create_vocabulary, untag_object

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Not Applied")

        with pytest.raises(TaxonomyValidationError):
            untag_object(term, article)


@pytest.mark.django_db
class TestGetTermsForObject:
    """Tests for get_terms_for_object()."""

    def test_returns_terms_for_tagged_object(self, db, article):
        """Returns terms associated with the object."""
        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            get_terms_for_object,
            tag_object,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A")
        term_b = create_term(vocabulary=vocab, name="B")
        tag_object(term_a, article)
        tag_object(term_b, article)

        terms = list(get_terms_for_object(article))
        assert len(terms) == 2
        pks = {t.pk for t in terms}
        assert term_a.pk in pks
        assert term_b.pk in pks

    def test_filters_by_vocabulary_instance(self, db, article):
        """Returns only terms from the specified vocabulary."""
        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            get_terms_for_object,
            tag_object,
        )

        vocab_a = create_vocabulary(name="A", vocabulary_type="flat")
        vocab_b = create_vocabulary(name="B", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab_a, name="Tag A")
        term_b = create_term(vocabulary=vocab_b, name="Tag B")
        tag_object(term_a, article)
        tag_object(term_b, article)

        terms = list(get_terms_for_object(article, vocabulary=vocab_a))
        assert len(terms) == 1
        assert terms[0].pk == term_a.pk

    def test_filters_by_vocabulary_slug(self, db, article):
        """Returns only terms from the vocabulary matching the slug."""
        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            get_terms_for_object,
            tag_object,
        )

        vocab_a = create_vocabulary(name="Alpha", slug="alpha", vocabulary_type="flat")
        vocab_b = create_vocabulary(name="Beta", slug="beta", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab_a, name="Tag Alpha")
        term_b = create_term(vocabulary=vocab_b, name="Tag Beta")
        tag_object(term_a, article)
        tag_object(term_b, article)

        terms = list(get_terms_for_object(article, vocabulary_slug="alpha"))
        assert len(terms) == 1
        assert terms[0].pk == term_a.pk

    def test_returns_empty_queryset_for_untagged_object(self, db, article):
        """Returns empty queryset for an untagged object."""
        from icv_taxonomy.services import get_terms_for_object

        terms = list(get_terms_for_object(article))
        assert terms == []


@pytest.mark.django_db
class TestGetObjectsForTerm:
    """Tests for get_objects_for_term()."""

    def test_returns_typed_queryset_when_model_class_given(self, db, article, product):
        """Returns a typed QuerySet when model_class is specified."""
        from taxonomy_testapp.models import Article

        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            get_objects_for_term,
            tag_object,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Tag")
        tag_object(term, article)
        tag_object(term, product)

        qs = get_objects_for_term(term, model_class=Article)
        assert article in qs
        assert product not in qs

    def test_returns_list_without_model_class(self, db, article, product):
        """Returns a list of mixed objects when no model_class specified."""
        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            get_objects_for_term,
            tag_object,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Tag")
        tag_object(term, article)
        tag_object(term, product)

        objects = get_objects_for_term(term)
        assert isinstance(objects, list)
        assert len(objects) == 2


@pytest.mark.django_db
class TestReplaceTermOnObject:
    """Tests for replace_term_on_object()."""

    def test_replaces_old_term_with_new_term(self, db, article):
        """New term is associated; old term is removed."""
        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            get_terms_for_object,
            replace_term_on_object,
            tag_object,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        old_term = create_term(vocabulary=vocab, name="Old")
        new_term = create_term(vocabulary=vocab, name="New")
        tag_object(old_term, article)

        replace_term_on_object(article, old_term, new_term)

        terms = list(get_terms_for_object(article))
        term_pks = {t.pk for t in terms}
        assert new_term.pk in term_pks
        assert old_term.pk not in term_pks


@pytest.mark.django_db
class TestBulkTagObjects:
    """Tests for bulk_tag_objects()."""

    def test_creates_associations_for_all_objects(self, db):
        """Associations are created for every object in the list."""
        from django.apps import apps
        from taxonomy_testapp.models import Article

        from icv_taxonomy.services import bulk_tag_objects, create_term, create_vocabulary

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Python")
        articles = [Article.objects.create(title=f"Article {i}") for i in range(3)]

        bulk_tag_objects(term, articles)

        TermAssociation = apps.get_model("icv_taxonomy", "TermAssociation")
        assert TermAssociation.objects.filter(term=term).count() == 3

    def test_skips_duplicates_silently(self, db, article):
        """Duplicate tags are silently ignored (ignore_conflicts)."""
        from django.apps import apps

        from icv_taxonomy.services import bulk_tag_objects, create_term, create_vocabulary

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Python")
        bulk_tag_objects(term, [article])
        # Second call with same article — should not raise.
        bulk_tag_objects(term, [article])

        TermAssociation = apps.get_model("icv_taxonomy", "TermAssociation")
        assert TermAssociation.objects.filter(term=term).count() == 1

    def test_raises_on_inactive_term(self, db, article):
        """Bulk-tagging with inactive term raises TaxonomyValidationError."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import (
            bulk_tag_objects,
            create_term,
            create_vocabulary,
            deactivate_term,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Inactive")
        deactivate_term(term)

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-017"):
            bulk_tag_objects(term, [article])


@pytest.mark.django_db
class TestCleanupOrphanedAssociations:
    """Tests for cleanup_orphaned_associations()."""

    def test_removes_orphaned_associations(self, db):
        """Associations for deleted objects are removed."""
        from django.apps import apps
        from taxonomy_testapp.models import Article

        from icv_taxonomy.services import (
            cleanup_orphaned_associations,
            create_term,
            create_vocabulary,
            tag_object,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Tag")
        article = Article.objects.create(title="To Delete")
        tag_object(term, article)

        # Delete the article, leaving the association orphaned.
        article.delete()

        result = cleanup_orphaned_associations(model_class=Article)
        assert result["orphaned"] > 0
        assert result["removed"] == result["orphaned"]

        TermAssociation = apps.get_model("icv_taxonomy", "TermAssociation")
        assert not TermAssociation.objects.filter(term=term).exists()

    def test_dry_run_does_not_delete(self, db):
        """dry_run=True reports orphans without deleting them."""
        from django.apps import apps
        from taxonomy_testapp.models import Article

        from icv_taxonomy.services import (
            cleanup_orphaned_associations,
            create_term,
            create_vocabulary,
            tag_object,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Tag")
        article = Article.objects.create(title="To Delete")
        tag_object(term, article)
        article.delete()

        result = cleanup_orphaned_associations(model_class=Article, dry_run=True)
        assert result["orphaned"] > 0
        assert result["removed"] == 0

        TermAssociation = apps.get_model("icv_taxonomy", "TermAssociation")
        assert TermAssociation.objects.filter(term=term).exists()


# ===========================================================================
# relationships
# ===========================================================================


@pytest.mark.django_db
class TestAddRelationship:
    """Tests for add_relationship()."""

    def test_creates_relationship(self, db):
        """A TermRelationship row is created."""
        from django.apps import apps

        from icv_taxonomy.services import add_relationship, create_term, create_vocabulary

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A")
        term_b = create_term(vocabulary=vocab, name="B")

        rel = add_relationship(term_a, term_b, "see_also")

        TermRelationship = apps.get_model("icv_taxonomy", "TermRelationship")
        assert TermRelationship.objects.filter(pk=rel.pk).exists()

    def test_creates_reciprocal_for_synonym(self, db):
        """Synonym relationship creates the reciprocal record (BR-TAX-020)."""
        from django.apps import apps

        from icv_taxonomy.services import add_relationship, create_term, create_vocabulary

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A")
        term_b = create_term(vocabulary=vocab, name="B")
        add_relationship(term_a, term_b, "synonym")

        TermRelationship = apps.get_model("icv_taxonomy", "TermRelationship")
        assert TermRelationship.objects.filter(term_from=term_b, term_to=term_a, relationship_type="synonym").exists()

    def test_creates_reciprocal_for_related(self, db):
        """Related relationship creates the reciprocal record (BR-TAX-020)."""
        from django.apps import apps

        from icv_taxonomy.services import add_relationship, create_term, create_vocabulary

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A")
        term_b = create_term(vocabulary=vocab, name="B")
        add_relationship(term_a, term_b, "related")

        TermRelationship = apps.get_model("icv_taxonomy", "TermRelationship")
        assert TermRelationship.objects.filter(term_from=term_b, term_to=term_a, relationship_type="related").exists()

    def test_does_not_create_reciprocal_for_see_also(self, db):
        """Directional relationship does NOT create a reciprocal."""
        from django.apps import apps

        from icv_taxonomy.services import add_relationship, create_term, create_vocabulary

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A")
        term_b = create_term(vocabulary=vocab, name="B")
        add_relationship(term_a, term_b, "see_also")

        TermRelationship = apps.get_model("icv_taxonomy", "TermRelationship")
        assert not TermRelationship.objects.filter(
            term_from=term_b, term_to=term_a, relationship_type="see_also"
        ).exists()

    def test_raises_on_self_relationship(self, db):
        """Self-relationship raises TaxonomyValidationError (BR-TAX-021)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import add_relationship, create_term, create_vocabulary

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="A")

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-021"):
            add_relationship(term, term, "synonym")

    def test_idempotent_for_existing_relationship(self, db):
        """Calling add_relationship twice does not create duplicates."""
        from django.apps import apps

        from icv_taxonomy.services import add_relationship, create_term, create_vocabulary

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A")
        term_b = create_term(vocabulary=vocab, name="B")
        add_relationship(term_a, term_b, "see_also")
        add_relationship(term_a, term_b, "see_also")

        TermRelationship = apps.get_model("icv_taxonomy", "TermRelationship")
        assert (
            TermRelationship.objects.filter(term_from=term_a, term_to=term_b, relationship_type="see_also").count() == 1
        )


@pytest.mark.django_db
class TestRemoveRelationship:
    """Tests for remove_relationship()."""

    def test_removes_relationship(self, db):
        """TermRelationship row is deleted."""
        from django.apps import apps

        from icv_taxonomy.services import (
            add_relationship,
            create_term,
            create_vocabulary,
            remove_relationship,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A")
        term_b = create_term(vocabulary=vocab, name="B")
        add_relationship(term_a, term_b, "see_also")
        remove_relationship(term_a, term_b, "see_also")

        TermRelationship = apps.get_model("icv_taxonomy", "TermRelationship")
        assert not TermRelationship.objects.filter(
            term_from=term_a, term_to=term_b, relationship_type="see_also"
        ).exists()

    def test_removes_reciprocal_for_synonym(self, db):
        """Removing synonym also removes the reciprocal record."""
        from django.apps import apps

        from icv_taxonomy.services import (
            add_relationship,
            create_term,
            create_vocabulary,
            remove_relationship,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A")
        term_b = create_term(vocabulary=vocab, name="B")
        add_relationship(term_a, term_b, "synonym")
        remove_relationship(term_a, term_b, "synonym")

        TermRelationship = apps.get_model("icv_taxonomy", "TermRelationship")
        assert (
            TermRelationship.objects.filter(term_from=term_b, term_to=term_a, relationship_type="synonym").count() == 0
        )


@pytest.mark.django_db
class TestGetRelatedTerms:
    """Tests for get_related_terms() and get_synonyms()."""

    def test_returns_related_terms(self, db):
        """Returns the target terms of outgoing relationships."""
        from icv_taxonomy.services import (
            add_relationship,
            create_term,
            create_vocabulary,
            get_related_terms,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A")
        term_b = create_term(vocabulary=vocab, name="B")
        term_c = create_term(vocabulary=vocab, name="C")
        add_relationship(term_a, term_b, "related")
        add_relationship(term_a, term_c, "see_also")

        related = list(get_related_terms(term_a))
        pks = {t.pk for t in related}
        assert term_b.pk in pks
        assert term_c.pk in pks

    def test_filters_by_relationship_type(self, db):
        """Returns only terms matching the specified relationship type."""
        from icv_taxonomy.services import (
            add_relationship,
            create_term,
            create_vocabulary,
            get_related_terms,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A")
        term_b = create_term(vocabulary=vocab, name="B")
        term_c = create_term(vocabulary=vocab, name="C")
        add_relationship(term_a, term_b, "synonym")
        add_relationship(term_a, term_c, "see_also")

        synonyms = list(get_related_terms(term_a, "synonym"))
        assert len(synonyms) == 1
        assert synonyms[0].pk == term_b.pk

    def test_get_synonyms_convenience(self, db):
        """get_synonyms() delegates to get_related_terms with type='synonym'."""
        from icv_taxonomy.services import (
            add_relationship,
            create_term,
            create_vocabulary,
            get_synonyms,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="Car")
        term_b = create_term(vocabulary=vocab, name="Automobile")
        add_relationship(term_a, term_b, "synonym")

        synonyms = list(get_synonyms(term_a))
        assert len(synonyms) == 1
        assert synonyms[0].pk == term_b.pk


# ===========================================================================
# import_export
# ===========================================================================


@pytest.mark.django_db
class TestExportVocabulary:
    """Tests for export_vocabulary()."""

    def test_exports_vocabulary_metadata(self, flat_vocabulary):
        """Export dict contains vocabulary metadata fields."""
        from icv_taxonomy.services import export_vocabulary

        data = export_vocabulary(flat_vocabulary)
        assert data["name"] == flat_vocabulary.name
        assert data["slug"] == flat_vocabulary.slug
        assert data["vocabulary_type"] == flat_vocabulary.vocabulary_type

    def test_exports_active_terms_by_default(self, flat_vocabulary):
        """Active terms are included in the export."""
        from icv_taxonomy.services import export_vocabulary

        data = export_vocabulary(flat_vocabulary)
        assert len(data["terms"]) > 0

    def test_excludes_inactive_terms_by_default(self, db):
        """Inactive terms are excluded unless include_inactive=True."""
        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            deactivate_term,
            export_vocabulary,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        active_term = create_term(vocabulary=vocab, name="Active")
        inactive_term = create_term(vocabulary=vocab, name="Inactive")
        deactivate_term(inactive_term)

        data = export_vocabulary(vocab)
        exported_slugs = {t["slug"] for t in data["terms"]}
        assert active_term.slug in exported_slugs
        assert inactive_term.slug not in exported_slugs

    def test_includes_inactive_when_requested(self, db):
        """include_inactive=True includes all terms."""
        from icv_taxonomy.services import (
            create_term,
            create_vocabulary,
            deactivate_term,
            export_vocabulary,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        active_term = create_term(vocabulary=vocab, name="Active")
        inactive_term = create_term(vocabulary=vocab, name="Inactive")
        deactivate_term(inactive_term)

        data = export_vocabulary(vocab, include_inactive=True)
        exported_slugs = {t["slug"] for t in data["terms"]}
        assert active_term.slug in exported_slugs
        assert inactive_term.slug in exported_slugs

    def test_exports_parent_slug_for_hierarchical_terms(self, db):
        """Hierarchical terms include parent_slug in the export."""
        from icv_taxonomy.services import create_term, create_vocabulary, export_vocabulary

        vocab = create_vocabulary(name="Topics", vocabulary_type="hierarchical")
        root = create_term(vocabulary=vocab, name="Root", slug="root")
        create_term(vocabulary=vocab, name="Child", slug="child", parent=root)

        data = export_vocabulary(vocab)
        term_map = {t["slug"]: t for t in data["terms"]}
        assert term_map["child"]["parent_slug"] == "root"
        assert term_map["root"]["parent_slug"] is None

    def test_exports_relationships(self, db):
        """Term relationships within the vocabulary are exported."""
        from icv_taxonomy.services import (
            add_relationship,
            create_term,
            create_vocabulary,
            export_vocabulary,
        )

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term_a = create_term(vocabulary=vocab, name="A", slug="a")
        term_b = create_term(vocabulary=vocab, name="B", slug="b")
        add_relationship(term_a, term_b, "see_also")

        data = export_vocabulary(vocab)
        assert any(
            r["term_from_slug"] == "a" and r["term_to_slug"] == "b" and r["relationship_type"] == "see_also"
            for r in data["relationships"]
        )


@pytest.mark.django_db
class TestImportVocabulary:
    """Tests for import_vocabulary()."""

    def test_creates_vocabulary_from_data(self, db):
        """import_vocabulary() creates a new vocabulary when none exists."""
        from icv_taxonomy.models import Vocabulary
        from icv_taxonomy.services import import_vocabulary

        data = {
            "name": "Imported Vocab",
            "slug": "imported-vocab",
            "vocabulary_type": "flat",
            "is_open": True,
            "allow_multiple": True,
            "max_depth": None,
            "metadata": {},
            "description": "",
            "terms": [
                {
                    "name": "Term One",
                    "slug": "term-one",
                    "description": "",
                    "parent_slug": None,
                    "is_active": True,
                    "metadata": {},
                }
            ],
            "relationships": [],
        }
        result = import_vocabulary(data)
        assert result["created"] == 1
        assert result["updated"] == 0
        assert Vocabulary.all_objects.filter(slug="imported-vocab").exists()

    def test_idempotent_on_second_import(self, db):
        """Second import updates existing terms, does not create duplicates (BR-TAX-031)."""
        from icv_taxonomy.models import Term
        from icv_taxonomy.services import import_vocabulary

        data = {
            "name": "My Vocab",
            "slug": "my-vocab",
            "vocabulary_type": "flat",
            "is_open": True,
            "allow_multiple": True,
            "max_depth": None,
            "description": "",
            "metadata": {},
            "terms": [
                {
                    "name": "Term One",
                    "slug": "term-one",
                    "description": "",
                    "parent_slug": None,
                    "is_active": True,
                    "metadata": {},
                }
            ],
            "relationships": [],
        }
        import_vocabulary(data)
        # Second import with same data — should update, not create.
        data["terms"][0]["name"] = "Term One Updated"
        result = import_vocabulary(data)

        assert result["updated"] == 1
        assert result["created"] == 0
        term = Term.all_objects.get(slug="term-one", vocabulary__slug="my-vocab")
        assert term.name == "Term One Updated"

    def test_raises_on_new_terms_in_closed_vocabulary(self, closed_vocabulary):
        """Importing new terms into a closed vocabulary raises (BR-TAX-032)."""
        from icv_taxonomy.exceptions import TaxonomyValidationError
        from icv_taxonomy.services import export_vocabulary, import_vocabulary

        data = export_vocabulary(closed_vocabulary)
        data["terms"].append(
            {
                "name": "Brand New Term",
                "slug": "brand-new-term",
                "description": "",
                "parent_slug": None,
                "is_active": True,
                "metadata": {},
            }
        )

        with pytest.raises(TaxonomyValidationError, match="BR-TAX-032"):
            import_vocabulary(data, vocabulary=closed_vocabulary)

    def test_imports_into_existing_vocabulary(self, db):
        """import_vocabulary() can import into an existing vocabulary."""
        from icv_taxonomy.models import Term
        from icv_taxonomy.services import create_vocabulary, import_vocabulary

        vocab = create_vocabulary(name="Existing", slug="existing", vocabulary_type="flat")
        data = {
            "terms": [
                {
                    "name": "New Term",
                    "slug": "new-term",
                    "description": "",
                    "parent_slug": None,
                    "is_active": True,
                    "metadata": {},
                }
            ],
            "relationships": [],
        }
        result = import_vocabulary(data, vocabulary=vocab)
        assert result["created"] == 1
        assert Term.all_objects.filter(slug="new-term", vocabulary=vocab).exists()

    def test_round_trip_export_import(self, db):
        """Exporting and re-importing a vocabulary is idempotent."""
        from icv_taxonomy.services import (
            add_relationship,
            create_term,
            create_vocabulary,
            export_vocabulary,
            import_vocabulary,
        )

        vocab = create_vocabulary(name="Round Trip", slug="round-trip", vocabulary_type="hierarchical")
        root = create_term(vocabulary=vocab, name="Root", slug="root")
        child = create_term(vocabulary=vocab, name="Child", slug="child", parent=root)
        add_relationship(root, child, "see_also")

        data = export_vocabulary(vocab)
        result = import_vocabulary(data)
        # All existing terms are updated (not recreated).
        assert result["created"] == 0
        assert result["updated"] == 2
