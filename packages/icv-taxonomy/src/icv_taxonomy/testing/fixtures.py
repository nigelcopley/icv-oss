"""Pytest fixtures for icv-taxonomy consuming projects.

Import these fixtures in your project's ``conftest.py`` using pytest's
plugin mechanism, or use them directly in test files.

Usage in conftest.py::

    from icv_taxonomy.testing.fixtures import (
        taxonomy_vocabulary,
        taxonomy_hierarchical_vocabulary,
        taxonomy_term,
    )
"""

from __future__ import annotations

import pytest


@pytest.fixture
def taxonomy_vocabulary(db):
    """Provide a flat vocabulary with 5 active terms for consuming project tests.

    Returns:
        A ``Vocabulary`` instance with 5 ``Term`` children, all active.
    """
    from icv_taxonomy.services import create_term, create_vocabulary

    vocab = create_vocabulary(
        name="Test Taxonomy Vocabulary",
        slug="test-taxonomy-vocabulary",
        vocabulary_type="flat",
        is_open=True,
    )
    for i in range(1, 6):
        create_term(vocabulary=vocab, name=f"Tag {i}")
    return vocab


@pytest.fixture
def taxonomy_hierarchical_vocabulary(db):
    """Provide a hierarchical vocabulary with a 2-level tree for consuming project tests.

    Structure::

        root
        ├── child-1
        └── child-2

    Returns:
        A ``Vocabulary`` instance with ``vocabulary_type="hierarchical"``.
    """
    from icv_taxonomy.services import create_term, create_vocabulary

    vocab = create_vocabulary(
        name="Test Hierarchical Vocabulary",
        slug="test-hierarchical-vocabulary",
        vocabulary_type="hierarchical",
        is_open=True,
    )
    root = create_term(vocabulary=vocab, name="Root Category", slug="root-category")
    create_term(vocabulary=vocab, name="Sub Category 1", slug="sub-category-1", parent=root)
    create_term(vocabulary=vocab, name="Sub Category 2", slug="sub-category-2", parent=root)
    return vocab


@pytest.fixture
def taxonomy_term(db, taxonomy_vocabulary):
    """Provide a single active term from ``taxonomy_vocabulary``.

    Returns:
        The first ``Term`` in ``taxonomy_vocabulary``.
    """
    return taxonomy_vocabulary.terms.first()
