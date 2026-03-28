"""factory-boy factories for icv-taxonomy models.

For use in both the package's own tests and consuming project test suites.

Usage::

    from icv_taxonomy.testing.factories import VocabularyFactory, TermFactory

    vocab = VocabularyFactory(vocabulary_type="hierarchical")
    root = RootTermFactory(vocabulary=vocab)
    child = ChildTermFactory(parent=root, vocabulary=vocab)
"""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory


class VocabularyFactory(DjangoModelFactory):
    """Factory for the default Vocabulary model.

    Generates unique names and slugs using a sequence counter so that
    multiple factories can coexist in the same test without slug conflicts.
    """

    name = factory.Sequence(lambda n: f"Vocab {n}")
    slug = factory.LazyAttribute(lambda obj: f"vocab-{obj.name.lower().replace(' ', '-')}")
    vocabulary_type = "flat"
    is_open = True
    allow_multiple = True
    is_active = True

    class Meta:
        model = "icv_taxonomy.Vocabulary"


class HierarchicalVocabularyFactory(VocabularyFactory):
    """Factory for hierarchical Vocabulary instances."""

    name = factory.Sequence(lambda n: f"Hierarchical Vocab {n}")
    vocabulary_type = "hierarchical"


class TermFactory(DjangoModelFactory):
    """Factory for the default Term model.

    Creates flat vocabulary terms (no parent). Use RootTermFactory or
    ChildTermFactory for hierarchical contexts.
    """

    vocabulary = factory.SubFactory(VocabularyFactory)
    name = factory.Sequence(lambda n: f"Term {n}")
    slug = factory.LazyAttribute(lambda obj: f"term-{obj.name.lower().replace(' ', '-')}")
    parent = None
    is_active = True

    class Meta:
        model = "icv_taxonomy.Term"


class RootTermFactory(TermFactory):
    """Factory for root terms in a hierarchical vocabulary.

    Creates a term with no parent inside a HierarchicalVocabularyFactory vocab.
    """

    vocabulary = factory.SubFactory(HierarchicalVocabularyFactory)
    name = factory.Sequence(lambda n: f"Root Term {n}")
    slug = factory.LazyAttribute(lambda obj: f"root-term-{obj.name.lower().replace(' ', '-')}")
    parent = None


class ChildTermFactory(TermFactory):
    """Factory for child terms in a hierarchical vocabulary.

    Automatically creates a root parent term via RootTermFactory and
    inherits the vocabulary from the parent.
    """

    parent = factory.SubFactory(RootTermFactory)
    vocabulary = factory.LazyAttribute(lambda obj: obj.parent.vocabulary)
    name = factory.Sequence(lambda n: f"Child Term {n}")
    slug = factory.LazyAttribute(lambda obj: f"child-term-{obj.name.lower().replace(' ', '-')}")


class TermRelationshipFactory(DjangoModelFactory):
    """Factory for TermRelationship instances.

    Both term_from and term_to default to flat vocabulary terms. For
    hierarchical contexts, pass term instances explicitly.
    """

    term_from = factory.SubFactory(TermFactory)
    term_to = factory.SubFactory(TermFactory)
    relationship_type = "related"

    class Meta:
        model = "icv_taxonomy.TermRelationship"


# ---------------------------------------------------------------------------
# TermAssociation helper
# ---------------------------------------------------------------------------


def create_tagged_object(term, model_factory, **factory_kwargs):
    """Create a model instance via ``model_factory`` and tag it with ``term``.

    This helper exists because TermAssociation uses a GenericForeignKey which
    makes a standard factory-boy SubFactory awkward. Using this function
    cleanly separates model creation from the tagging step.

    Args:
        term: The Term instance to apply as a tag.
        model_factory: A factory-boy factory class whose ``create()`` method
            produces a Django model instance.
        **factory_kwargs: Additional keyword arguments forwarded to
            ``model_factory.create()``.

    Returns:
        The newly created model instance (already tagged).

    Example::

        article = create_tagged_object(term, ArticleFactory)
        assert article.pk is not None
    """
    from icv_taxonomy.services import tag_object

    obj = model_factory.create(**factory_kwargs)
    tag_object(term, obj)
    return obj
