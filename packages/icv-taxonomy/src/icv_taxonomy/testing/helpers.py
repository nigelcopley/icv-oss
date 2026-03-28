"""Test helper functions for icv-taxonomy.

Provides assertion helpers and utilities for testing taxonomy-related code
in consuming projects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def assert_term_tree_valid(vocabulary: Any) -> None:
    """Assert that all terms in a vocabulary have consistent tree fields.

    Validates:
    - Every term's ``depth`` matches ``path.count("/")``
    - Every term with a parent has ``path`` starting with ``parent.path + "/"``
    - Root terms (``parent=None``) have ``depth == 0``
    - No term's slug collides with another term in the same vocabulary

    Args:
        vocabulary: The Vocabulary instance to validate.

    Raises:
        AssertionError: If any term fails the consistency checks.
    """
    from icv_taxonomy.conf import get_term_model

    Term = get_term_model()
    terms = list(Term.all_objects.filter(vocabulary=vocabulary).select_related("parent").order_by("path"))

    seen_slugs: set[str] = set()
    for term in terms:
        # Slug uniqueness within vocabulary.
        assert term.slug not in seen_slugs, f"Duplicate slug '{term.slug}' found in vocabulary '{vocabulary.slug}'"
        seen_slugs.add(term.slug)

        # Depth matches path separator count.
        expected_depth = term.path.count("/")
        assert term.depth == expected_depth, (
            f"Term '{term.slug}': depth={term.depth} but path '{term.path}' implies depth={expected_depth}"
        )

        if term.parent_id is None:
            # Root terms must be at depth 0.
            assert term.depth == 0, f"Term '{term.slug}' has no parent but depth={term.depth}"
        else:
            # Child path must start with parent path.
            parent = term.parent
            assert term.path.startswith(parent.path + "/"), (
                f"Term '{term.slug}' path '{term.path}' does not start with parent path '{parent.path}/'"
            )


def create_tagged_object(term: Any, model_factory: Any, **factory_kwargs: Any) -> Any:
    """Create a model instance via ``model_factory`` and tag it with ``term``.

    Convenience helper for tests that need to tag objects without manually
    calling ``tag_object`` after factory creation.

    Args:
        term: The Term instance to apply as a tag.
        model_factory: A factory-boy factory class.
        **factory_kwargs: Keyword arguments forwarded to ``model_factory.create()``.

    Returns:
        The newly created model instance (already tagged with ``term``).
    """
    from icv_taxonomy.services import tag_object

    obj = model_factory.create(**factory_kwargs)
    tag_object(term, obj)
    return obj
