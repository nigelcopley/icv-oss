"""Tests for icv-taxonomy models.

Covers Vocabulary, Term, TermRelationship, and TermAssociation model
behaviour including managers, clean() rules, and constraints.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction


@pytest.mark.django_db
class TestVocabularyCreation:
    """Test Vocabulary model creation happy paths."""

    def test_create_vocabulary_persists_to_db(self, db):
        """Creating a vocabulary saves it to the database."""
        from icv_taxonomy.models import Vocabulary

        vocab = Vocabulary.objects.create(name="Colours", slug="colours")
        assert vocab.pk is not None
        assert Vocabulary.objects.filter(slug="colours").exists()

    def test_vocabulary_str_returns_name(self, db):
        """__str__ returns the vocabulary name."""
        from icv_taxonomy.models import Vocabulary

        vocab = Vocabulary(name="Colours", slug="colours")
        assert str(vocab) == "Colours"

    def test_vocabulary_defaults(self, db):
        """Newly created vocabulary has expected default field values."""
        from icv_taxonomy.models import Vocabulary

        vocab = Vocabulary.objects.create(name="Tags", slug="tags")
        assert vocab.vocabulary_type == "flat"
        assert vocab.is_open is True
        assert vocab.allow_multiple is True
        assert vocab.is_active is True
        assert vocab.max_depth is None
        assert vocab.metadata == {}


@pytest.mark.django_db
class TestVocabularySlugUniqueness:
    """Test BR-TAX-001: Vocabulary slug uniqueness."""

    def test_duplicate_slug_raises_integrity_error(self, db):
        """Creating two vocabularies with the same slug raises IntegrityError."""
        from icv_taxonomy.models import Vocabulary

        Vocabulary.objects.create(name="Colours", slug="colours")
        with pytest.raises(IntegrityError), transaction.atomic():
            Vocabulary.objects.create(name="Colours Alt", slug="colours")

    def test_same_slug_in_different_capitalisations_are_distinct_when_case_sensitive(self, db, settings):
        """When CASE_SENSITIVE_SLUGS=True, 'ColoursCS' and 'colourscs' are different slugs."""
        settings.ICV_TAXONOMY_CASE_SENSITIVE_SLUGS = True
        from icv_taxonomy.models import Vocabulary

        Vocabulary.objects.create(name="Colours CS Upper", slug="ColoursCS")
        # Lower-case should succeed if case-sensitive.
        v2 = Vocabulary.objects.create(name="Colours CS Lower", slug="colourscs")
        assert v2.slug == "colourscs"


@pytest.mark.django_db
class TestVocabularyTypeImmutability:
    """Test BR-TAX-002: vocabulary_type is immutable after terms exist."""

    def test_type_change_with_terms_raises_validation_error(self, db):
        """Changing vocabulary_type after terms exist raises ValidationError."""
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Changing Vocab", slug="changing-vocab", vocabulary_type="flat")
        Term(vocabulary=vocab, name="Alpha", slug="alpha").save()

        vocab.vocabulary_type = "hierarchical"
        with pytest.raises(ValidationError):
            vocab.full_clean()

    def test_type_change_without_terms_succeeds(self, db):
        """Changing vocabulary_type when no terms exist is allowed."""
        from icv_taxonomy.models import Vocabulary

        vocab = Vocabulary.objects.create(name="Empty Vocab", slug="empty-vocab", vocabulary_type="flat")
        vocab.vocabulary_type = "hierarchical"
        vocab.full_clean()  # should not raise
        vocab.save()
        vocab.refresh_from_db()
        assert vocab.vocabulary_type == "hierarchical"


@pytest.mark.django_db
class TestVocabularyAutoSlug:
    """Test BR-TAX-043: auto-slug generation from vocabulary name."""

    def test_auto_slug_generated_from_name(self, db, settings):
        """When slug is blank and AUTO_SLUG is True, slug is derived from name."""
        settings.ICV_TAXONOMY_AUTO_SLUG = True
        from icv_taxonomy.models import Vocabulary

        vocab = Vocabulary(name="Product Colours Unique XYZ")
        vocab.save()
        assert vocab.slug == "product-colours-unique-xyz"

    def test_auto_slug_collision_gets_suffix(self, db, settings):
        """When the generated slug already exists, a numeric suffix is appended."""
        settings.ICV_TAXONOMY_AUTO_SLUG = True
        from icv_taxonomy.services import create_vocabulary

        # Use the service which has collision-resolution logic (BR-TAX-043).
        create_vocabulary(name="Slug Collision A", slug="slug-collision")
        vocab2 = create_vocabulary(name="Slug Collision B", slug="slug-collision")
        assert vocab2.slug == "slug-collision-2"

    def test_auto_slug_disabled_does_not_auto_generate(self, db, settings):
        """When AUTO_SLUG is False, the slug is NOT auto-generated from name."""
        settings.ICV_TAXONOMY_AUTO_SLUG = False
        from icv_taxonomy.models import Vocabulary

        vocab = Vocabulary(name="Auto Slug Disabled Test", slug="")
        vocab.save()
        # With AUTO_SLUG=False, save() does not set the slug from name.
        assert vocab.slug == ""


@pytest.mark.django_db
class TestVocabularySlugCaseSensitivity:
    """Test BR-TAX-034: slug case sensitivity behaviour."""

    def test_slug_lowercased_when_case_insensitive(self, db, settings):
        """When CASE_SENSITIVE_SLUGS is False, slug is stored in lowercase."""
        settings.ICV_TAXONOMY_CASE_SENSITIVE_SLUGS = False
        from icv_taxonomy.models import Vocabulary

        vocab = Vocabulary(name="Something Case Test ABCD", slug="Dark-Blue-Unique-9999")
        vocab.save()
        assert vocab.slug == "dark-blue-unique-9999"


@pytest.mark.django_db
class TestVocabularyActiveManager:
    """Test BR-TAX-005: inactive vocabularies excluded from default manager."""

    def test_default_manager_excludes_inactive(self, db):
        """Vocabulary.objects.all() excludes is_active=False vocabularies."""
        from icv_taxonomy.models import Vocabulary

        Vocabulary.objects.create(name="Active", slug="active", is_active=True)
        Vocabulary.objects.create(name="Inactive", slug="inactive", is_active=False)

        names = list(Vocabulary.objects.values_list("name", flat=True))
        assert "Active" in names
        assert "Inactive" not in names

    def test_all_objects_includes_inactive(self, db):
        """Vocabulary.all_objects.all() includes both active and inactive."""
        from icv_taxonomy.models import Vocabulary

        Vocabulary.objects.create(name="Active", slug="active-v2", is_active=True)
        Vocabulary.objects.create(name="Inactive", slug="inactive-v2", is_active=False)

        names = list(Vocabulary.all_objects.values_list("name", flat=True))
        assert "Active" in names
        assert "Inactive" in names


@pytest.mark.django_db
class TestTermCreationWithAutoSlug:
    """Test BR-TAX-007: term auto-slug generation."""

    def test_term_auto_slug_from_name(self, db, settings):
        """Term gets slug auto-generated from name when slug is blank."""
        settings.ICV_TAXONOMY_AUTO_SLUG = True
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Colors", slug="colors")
        term = Term(vocabulary=vocab, name="Dark Blue")
        term.save()
        assert term.slug == "dark-blue"

    def test_term_auto_slug_collision_gets_suffix(self, db, settings):
        """Term slug collision is resolved by appending -2, -3."""
        settings.ICV_TAXONOMY_AUTO_SLUG = True
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Colors", slug="colors-2")
        t1 = Term(vocabulary=vocab, name="Dark Blue")
        t1.save()
        assert t1.slug == "dark-blue"

        t2 = Term(vocabulary=vocab, name="Dark Blue")
        t2.save()
        assert t2.slug == "dark-blue-2"

        t3 = Term(vocabulary=vocab, name="Dark Blue")
        t3.save()
        assert t3.slug == "dark-blue-3"


@pytest.mark.django_db
class TestTermSlugUniqueness:
    """Test BR-TAX-006: term slug unique within vocabulary."""

    def test_duplicate_slug_in_same_vocabulary_raises_integrity_error(self, db):
        """Two terms with the same slug in the same vocabulary raises IntegrityError."""
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Topics", slug="topics")
        Term.objects.create(vocabulary=vocab, name="Red", slug="red")
        with pytest.raises(IntegrityError), transaction.atomic():
            Term.objects.create(vocabulary=vocab, name="Red Alt", slug="red")

    def test_same_slug_in_different_vocabularies_is_allowed(self, db):
        """The same slug may appear in different vocabularies."""
        from icv_taxonomy.models import Term, Vocabulary

        v1 = Vocabulary.objects.create(name="Vocab A", slug="vocab-a")
        v2 = Vocabulary.objects.create(name="Vocab B", slug="vocab-b")
        t1 = Term.objects.create(vocabulary=v1, name="Red", slug="red")
        t2 = Term.objects.create(vocabulary=v2, name="Red", slug="red")
        assert t1.pk != t2.pk


@pytest.mark.django_db
class TestFlatVocabularyRejectsParent:
    """Test BR-TAX-008: flat vocabulary terms must have no parent."""

    def test_flat_term_with_parent_raises_validation_error(self, db, settings):
        """Creating a term with a parent in a flat vocabulary raises ValidationError."""
        settings.ICV_TAXONOMY_ENFORCE_VOCABULARY_TYPE = True
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Flat", slug="flat-test", vocabulary_type="flat")
        root = Term(vocabulary=vocab, name="Root", slug="root-flat")
        root.save()

        child = Term(vocabulary=vocab, name="Child", slug="child-flat", parent=root)
        with pytest.raises(ValidationError):
            child.full_clean()

    def test_flat_term_with_parent_allowed_when_enforcement_disabled(self, db, settings):
        """With ENFORCE_VOCABULARY_TYPE=False, flat vocab terms may have parents."""
        settings.ICV_TAXONOMY_ENFORCE_VOCABULARY_TYPE = False
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Permissive", slug="permissive", vocabulary_type="flat")
        root = Term(vocabulary=vocab, name="Root", slug="root-permissive")
        root.save()

        child = Term(vocabulary=vocab, name="Child", slug="child-permissive", parent=root)
        child.full_clean()  # should not raise
        child.save()
        assert child.parent_id == root.pk


@pytest.mark.django_db
class TestMaxDepthEnforcement:
    """Test BR-TAX-009: max_depth enforcement."""

    def test_term_exceeding_max_depth_raises_validation_error(self, db):
        """A term at depth > max_depth raises ValidationError."""
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(
            name="Shallow",
            slug="shallow",
            vocabulary_type="hierarchical",
            max_depth=1,
        )
        root = Term(vocabulary=vocab, name="Root", slug="root-shallow")
        root.save()
        root.refresh_from_db()

        depth_1 = Term(vocabulary=vocab, name="L1", slug="l1-shallow", parent=root)
        depth_1.save()
        depth_1.refresh_from_db()

        depth_2 = Term(vocabulary=vocab, name="L2", slug="l2-shallow", parent=depth_1)
        with pytest.raises(ValidationError):
            depth_2.full_clean()


@pytest.mark.django_db
class TestCrossVocabularyParentRejection:
    """Test BR-TAX-014: parent must belong to same vocabulary."""

    def test_cross_vocabulary_parent_raises_validation_error(self, db):
        """A term with a parent from a different vocabulary raises ValidationError."""
        from icv_taxonomy.models import Term, Vocabulary

        v1 = Vocabulary.objects.create(name="Vocab X", slug="vocab-x", vocabulary_type="hierarchical")
        v2 = Vocabulary.objects.create(name="Vocab Y", slug="vocab-y", vocabulary_type="hierarchical")
        root = Term(vocabulary=v1, name="Root", slug="root-x")
        root.save()

        term = Term(vocabulary=v2, name="Child", slug="child-y", parent=root)
        with pytest.raises(ValidationError):
            term.full_clean()


@pytest.mark.django_db
class TestClosedVocabularyRejectsNewTerms:
    """Test BR-TAX-003: closed vocabularies reject new terms."""

    def test_closed_vocabulary_rejects_new_term_via_clean(self, db):
        """Adding a term to a closed vocabulary raises ValidationError."""
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Closed", slug="closed-test", is_open=False)
        term = Term(vocabulary=vocab, name="New Term", slug="new-term")
        with pytest.raises(ValidationError):
            term.full_clean()


@pytest.mark.django_db
class TestVocabularyImmutabilityOnTerm:
    """Test BR-TAX-010: term vocabulary cannot change after creation."""

    def test_changing_term_vocabulary_raises_validation_error(self, db):
        """Changing a term's vocabulary after creation raises ValidationError."""
        from icv_taxonomy.models import Term, Vocabulary

        v1 = Vocabulary.objects.create(name="V1", slug="v1-test")
        v2 = Vocabulary.objects.create(name="V2", slug="v2-test")
        term = Term.objects.create(vocabulary=v1, name="Term", slug="term-immutable")

        term.vocabulary = v2
        with pytest.raises(ValidationError):
            term.full_clean()


@pytest.mark.django_db
class TestInactiveTermManager:
    """Test BR-TAX-012: inactive terms excluded from default manager."""

    def test_default_manager_excludes_inactive_terms(self, db):
        """Term.objects.all() excludes is_active=False terms."""
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Manager Test", slug="manager-test")
        Term.objects.create(vocabulary=vocab, name="Active", slug="active-term")
        inactive = Term(vocabulary=vocab, name="Inactive", slug="inactive-term")
        inactive.is_active = False
        inactive.save()

        slugs = list(Term.objects.filter(vocabulary=vocab).values_list("slug", flat=True))
        assert "active-term" in slugs
        assert "inactive-term" not in slugs

    def test_all_objects_includes_inactive_terms(self, db):
        """Term.all_objects.all() includes inactive terms."""
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="All Objects Test", slug="all-objects-test")
        Term.objects.create(vocabulary=vocab, name="Active", slug="active-t")
        inactive = Term(vocabulary=vocab, name="Inactive", slug="inactive-t")
        inactive.is_active = False
        inactive.save()

        slugs = list(Term.all_objects.filter(vocabulary=vocab).values_list("slug", flat=True))
        assert "active-t" in slugs
        assert "inactive-t" in slugs


@pytest.mark.django_db
class TestDeactivateTermPreservesAssociations:
    """Test BR-TAX-013: deactivating term preserves associations."""

    def test_deactivate_preserves_existing_associations(self, db, flat_vocabulary, article):
        """Deactivating a term does not delete its TermAssociation records."""
        from icv_taxonomy.models import TermAssociation
        from icv_taxonomy.services import tag_object

        term = flat_vocabulary.terms.first()
        tag_object(term, article)

        # Deactivate the term directly.
        term.is_active = False
        term.save(update_fields=["is_active"])

        # The association must still exist.
        assert TermAssociation.objects.filter(term=term).exists()


@pytest.mark.django_db
class TestTermRelationshipSelfReferenceRejection:
    """Test BR-TAX-021: self-referential relationships are rejected."""

    def test_self_relationship_raises_validation_error(self, db):
        """A TermRelationship where term_from == term_to raises ValidationError."""
        from icv_taxonomy.models import Term, TermRelationship, Vocabulary

        vocab = Vocabulary.objects.create(name="Rel Vocab", slug="rel-vocab")
        term = Term.objects.create(vocabulary=vocab, name="Alpha", slug="alpha-self")

        rel = TermRelationship(term_from=term, term_to=term, relationship_type="synonym")
        with pytest.raises(ValidationError):
            rel.full_clean()


@pytest.mark.django_db
class TestTermRelationshipUniqueness:
    """Test BR-TAX-022: relationship uniqueness per pair/type."""

    def test_duplicate_relationship_raises_integrity_error(self, db):
        """Creating two identical TermRelationship rows raises IntegrityError."""
        from icv_taxonomy.models import Term, TermRelationship, Vocabulary

        vocab = Vocabulary.objects.create(name="Uniqueness", slug="uniqueness")
        a = Term.objects.create(vocabulary=vocab, name="A", slug="a-unique")
        b = Term.objects.create(vocabulary=vocab, name="B", slug="b-unique")

        TermRelationship.objects.create(term_from=a, term_to=b, relationship_type="synonym")
        with pytest.raises(IntegrityError), transaction.atomic():
            TermRelationship.objects.create(term_from=a, term_to=b, relationship_type="synonym")

    def test_different_relationship_type_is_allowed(self, db):
        """The same pair may have multiple relationship types."""
        from icv_taxonomy.models import Term, TermRelationship, Vocabulary

        vocab = Vocabulary.objects.create(name="Multi Rel", slug="multi-rel")
        a = Term.objects.create(vocabulary=vocab, name="A", slug="a-multi")
        b = Term.objects.create(vocabulary=vocab, name="B", slug="b-multi")

        TermRelationship.objects.create(term_from=a, term_to=b, relationship_type="synonym")
        TermRelationship.objects.create(term_from=a, term_to=b, relationship_type="related")
        assert TermRelationship.objects.filter(term_from=a, term_to=b).count() == 2


@pytest.mark.django_db
class TestTermAssociationUniqueness:
    """Test BR-TAX-015: TermAssociation uniqueness per (term, content_type, object_id)."""

    def test_duplicate_association_raises_integrity_error(self, db, article):
        """Tagging the same object with the same term twice raises IntegrityError."""
        from django.contrib.contenttypes.models import ContentType

        from icv_taxonomy.models import Term, TermAssociation, Vocabulary

        vocab = Vocabulary.objects.create(name="Assoc Unique", slug="assoc-unique")
        term = Term.objects.create(vocabulary=vocab, name="Tag", slug="tag-assoc")
        ct = ContentType.objects.get_for_model(article)

        TermAssociation.objects.create(term=term, content_type=ct, object_id=str(article.pk))
        with pytest.raises(IntegrityError), transaction.atomic():
            TermAssociation.objects.create(term=term, content_type=ct, object_id=str(article.pk))


@pytest.mark.django_db
class TestVocabularyDeletionCascades:
    """Test BR-TAX-004: vocabulary deletion cascades to terms and associations."""

    def test_delete_vocabulary_removes_all_terms(self, db):
        """Deleting a vocabulary cascades to all its terms."""
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Cascade Vocab", slug="cascade-vocab")
        for i in range(5):
            Term.objects.create(vocabulary=vocab, name=f"Term {i}", slug=f"term-cascade-{i}")
        vocab_pk = vocab.pk
        vocab.delete()

        assert not Term.all_objects.filter(vocabulary_id=vocab_pk).exists()

    def test_delete_vocabulary_removes_associations(self, db, article):
        """Deleting a vocabulary cascades to term associations."""
        from icv_taxonomy.models import Term, TermAssociation, Vocabulary
        from icv_taxonomy.services import tag_object

        vocab = Vocabulary.objects.create(name="Cascade Assoc Vocab", slug="cascade-assoc-vocab")
        term = Term.objects.create(vocabulary=vocab, name="Cascade Term", slug="cascade-term")
        tag_object(term, article)

        assert TermAssociation.objects.filter(term=term).exists()
        vocab.delete()
        assert not TermAssociation.objects.filter(term_id=term.pk).exists()


@pytest.mark.django_db
class TestCrossVocabularyPathCollision:
    """Regression tests for GitHub issue #2: path collision across vocabularies.

    Verifies that terms in different vocabularies get independent path
    numbering and that rebuild() does not produce cross-vocabulary collisions.
    """

    def test_terms_in_different_flat_vocabs_get_same_paths(self, db):
        """Root terms in different vocabularies should both start at path '0001'."""
        from icv_taxonomy.models import Term, Vocabulary

        v1 = Vocabulary.objects.create(name="Path A", slug="path-a", vocabulary_type="flat")
        v2 = Vocabulary.objects.create(name="Path B", slug="path-b", vocabulary_type="flat")

        t1 = Term.objects.create(vocabulary=v1, name="A-1", slug="a-1")
        t2 = Term.objects.create(vocabulary=v2, name="B-1", slug="b-1")
        t1.refresh_from_db()
        t2.refresh_from_db()

        assert t1.path == "0001"
        assert t2.path == "0001"

    def test_many_terms_across_flat_vocabs_no_collision(self, db):
        """Creating many terms across two flat vocabularies should not raise IntegrityError."""
        from icv_taxonomy.models import Term, Vocabulary

        v1 = Vocabulary.objects.create(name="Many A", slug="many-a", vocabulary_type="flat")
        v2 = Vocabulary.objects.create(name="Many B", slug="many-b", vocabulary_type="flat")

        for i in range(20):
            Term.objects.create(vocabulary=v1, name=f"A-{i}", slug=f"a-{i}")
            Term.objects.create(vocabulary=v2, name=f"B-{i}", slug=f"b-{i}")

        assert Term.all_objects.filter(vocabulary=v1).count() == 20
        assert Term.all_objects.filter(vocabulary=v2).count() == 20

    def test_rebuild_with_multiple_flat_vocabs_no_collision(self, db):
        """rebuild() should not raise IntegrityError across multiple flat vocabularies."""
        from icv_taxonomy.models import Term, Vocabulary

        v1 = Vocabulary.objects.create(name="Rebuild A", slug="rebuild-a", vocabulary_type="flat")
        v2 = Vocabulary.objects.create(name="Rebuild B", slug="rebuild-b", vocabulary_type="flat")

        for i in range(10):
            Term.objects.create(vocabulary=v1, name=f"RA-{i}", slug=f"ra-{i}")
            Term.objects.create(vocabulary=v2, name=f"RB-{i}", slug=f"rb-{i}")

        # Corrupt paths, then rebuild — should succeed.
        for term in Term.all_objects.all():
            Term.all_objects.filter(pk=term.pk).update(
                path=f"CORRUPT_{term.pk}", depth=99, order=99,
            )

        result = Term.all_objects.rebuild()
        assert result["nodes_updated"] == 20

        # Each vocab should have paths 0001..0010 independently.
        v1_paths = sorted(Term.all_objects.filter(vocabulary=v1).values_list("path", flat=True))
        v2_paths = sorted(Term.all_objects.filter(vocabulary=v2).values_list("path", flat=True))
        expected = [f"{str(i + 1).zfill(4)}" for i in range(10)]
        assert v1_paths == expected
        assert v2_paths == expected

    def test_rebuild_with_hierarchical_vocab_alongside_flat(self, db):
        """rebuild() handles mixed vocabulary types correctly."""
        from icv_taxonomy.models import Term, Vocabulary

        flat = Vocabulary.objects.create(name="Flat Mixed", slug="flat-mixed", vocabulary_type="flat")
        hier = Vocabulary.objects.create(name="Hier Mixed", slug="hier-mixed", vocabulary_type="hierarchical")

        # Flat terms.
        for i in range(5):
            Term.objects.create(vocabulary=flat, name=f"F-{i}", slug=f"f-{i}")

        # Hierarchical terms.
        root = Term(vocabulary=hier, name="Root", slug="root-mixed")
        root.save()
        root.refresh_from_db()
        child = Term(vocabulary=hier, name="Child", slug="child-mixed", parent=root)
        child.save()
        child.refresh_from_db()

        # Corrupt and rebuild.
        for term in Term.all_objects.all():
            Term.all_objects.filter(pk=term.pk).update(
                path=f"CORRUPT_{term.pk}", depth=99, order=99,
            )

        Term.all_objects.rebuild()

        root.refresh_from_db()
        child.refresh_from_db()
        assert root.path == "0001"
        assert child.path == "0001/0001"

        flat_paths = sorted(Term.all_objects.filter(vocabulary=flat).values_list("path", flat=True))
        assert flat_paths == [f"{str(i + 1).zfill(4)}" for i in range(5)]
