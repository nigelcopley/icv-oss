"""Shared pytest fixtures and configuration for icv-taxonomy tests."""

from __future__ import annotations

import pytest


def pytest_configure(config) -> None:  # type: ignore[no-untyped-def]
    """Ensure icv_taxonomy and taxonomy_testapp are in INSTALLED_APPS."""
    from django.conf import settings

    if not settings.configured:
        return

    for app in ("icv_taxonomy", "taxonomy_testapp"):
        if app not in settings.INSTALLED_APPS:
            settings.INSTALLED_APPS = [*settings.INSTALLED_APPS, app]

    if not hasattr(settings, "MIGRATION_MODULES"):
        settings.MIGRATION_MODULES = {}
    settings.MIGRATION_MODULES.setdefault("icv_taxonomy", None)
    settings.MIGRATION_MODULES.setdefault("taxonomy_testapp", None)

    # Ensure icv-tree settings have sensible test defaults.
    tree_defaults = {
        "ICV_TREE_PATH_SEPARATOR": "/",
        "ICV_TREE_STEP_LENGTH": 4,
        "ICV_TREE_MAX_PATH_LENGTH": 255,
        "ICV_TREE_ENABLE_CTE": False,
        "ICV_TREE_REBUILD_BATCH_SIZE": 1000,
        "ICV_TREE_CHECK_ON_SAVE": False,
    }
    for key, value in tree_defaults.items():
        if not hasattr(settings, key):
            setattr(settings, key, value)

    # Ensure icv-taxonomy settings have sensible test defaults.
    taxonomy_defaults = {
        "ICV_TAXONOMY_AUTO_SLUG": True,
        "ICV_TAXONOMY_CASE_SENSITIVE_SLUGS": False,
        "ICV_TAXONOMY_ENFORCE_VOCABULARY_TYPE": True,
    }
    for key, value in taxonomy_defaults.items():
        if not hasattr(settings, key):
            setattr(settings, key, value)


# ---------------------------------------------------------------------------
# Model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def article(db):
    """Create and return a persisted Article instance."""
    from taxonomy_testapp.models import Article

    return Article.objects.create(title="Test Article")


@pytest.fixture
def product(db):
    """Create and return a persisted Product instance."""
    from taxonomy_testapp.models import Product

    return Product.objects.create(name="Test Product")


# ---------------------------------------------------------------------------
# Vocabulary fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def flat_vocabulary(db):
    """Create a flat vocabulary with 5 active terms."""
    from icv_taxonomy.services import create_term, create_vocabulary

    vocab = create_vocabulary(
        name="Flat Vocab",
        slug="flat-vocab",
        vocabulary_type="flat",
        is_open=True,
    )
    for i in range(1, 6):
        create_term(vocabulary=vocab, name=f"Term {i}")
    return vocab


@pytest.fixture
def hierarchical_vocabulary(db):
    """Create a hierarchical vocabulary with a 3-level tree.

    Structure::

        root
        ├── child-1
        │   ├── grandchild-1-1
        │   └── grandchild-1-2
        ├── child-2
        │   ├── grandchild-2-1
        │   └── grandchild-2-2
        └── child-3
            ├── grandchild-3-1
            └── grandchild-3-2
    """
    from icv_taxonomy.services import create_term, create_vocabulary

    vocab = create_vocabulary(
        name="Hierarchical Vocab",
        slug="hierarchical-vocab",
        vocabulary_type="hierarchical",
        is_open=True,
    )
    root = create_term(vocabulary=vocab, name="Root", slug="root")
    for child_n in range(1, 4):
        child = create_term(
            vocabulary=vocab,
            name=f"Child {child_n}",
            slug=f"child-{child_n}",
            parent=root,
        )
        for gc_n in range(1, 3):
            create_term(
                vocabulary=vocab,
                name=f"Grandchild {child_n}-{gc_n}",
                slug=f"grandchild-{child_n}-{gc_n}",
                parent=child,
            )
    return vocab


@pytest.fixture
def closed_vocabulary(db):
    """Create a closed vocabulary with 3 active terms."""
    from icv_taxonomy.models import Term, Vocabulary

    vocab = Vocabulary.objects.create(
        name="Closed Vocab",
        slug="closed-vocab",
        vocabulary_type="flat",
        is_open=False,
    )
    # Create terms by bypassing the closed check (terms are added at open time,
    # then the vocabulary is closed).
    for i in range(1, 4):
        term = Term(vocabulary=vocab, name=f"Fixed Term {i}", slug=f"fixed-term-{i}")
        term.save()
    return vocab


@pytest.fixture
def single_term_vocabulary(db):
    """Create a flat vocabulary with allow_multiple=False and 3 terms."""
    from icv_taxonomy.services import create_term, create_vocabulary

    vocab = create_vocabulary(
        name="Single Term Vocab",
        slug="single-term-vocab",
        vocabulary_type="flat",
        is_open=True,
        allow_multiple=False,
    )
    for i in range(1, 4):
        create_term(vocabulary=vocab, name=f"Option {i}")
    return vocab


# ---------------------------------------------------------------------------
# Tagged object fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def tagged_article(db, flat_vocabulary, article):
    """Return an Article tagged with the first term from flat_vocabulary."""
    from icv_taxonomy.services import tag_object

    term = flat_vocabulary.terms.first()
    tag_object(term, article)
    return article
