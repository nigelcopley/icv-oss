"""icv-taxonomy testing utilities for consuming projects.

This package provides factory-boy factories, pytest fixtures, and assertion
helpers for testing code that integrates with icv-taxonomy.

Usage in consuming project tests::

    from icv_taxonomy.testing import assert_term_tree_valid
    from icv_taxonomy.testing.factories import VocabularyFactory, TermFactory
    from icv_taxonomy.testing.fixtures import taxonomy_vocabulary, taxonomy_term
"""

from __future__ import annotations

from .helpers import assert_term_tree_valid, create_tagged_object

__all__ = [
    "assert_term_tree_valid",
    "create_tagged_object",
]
