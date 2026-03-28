"""Tests for icv-taxonomy signal emissions.

Each test connects a handler to a signal, triggers the relevant action,
and asserts the handler was called with the expected keyword arguments.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SignalCapture:
    """Minimal signal capture helper.

    Usage::

        cap = _SignalCapture()
        some_signal.connect(cap, weak=False)
        ...
        assert cap.called_once()
        assert cap.last_kwargs["term"].slug == "red"
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, **kwargs) -> None:
        self.calls.append(kwargs)

    def called_once(self) -> bool:
        return len(self.calls) == 1

    @property
    def last_kwargs(self) -> dict:
        return self.calls[-1]

    def clear(self) -> None:
        self.calls.clear()


# ---------------------------------------------------------------------------
# Vocabulary lifecycle signals
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVocabularyCreatedSignal:
    """Test AC-TAX-048: vocabulary_created emitted on vocabulary creation."""

    def test_vocabulary_created_signal_emitted_on_create(self, db):
        """vocabulary_created is emitted when create_vocabulary() is called."""
        from icv_taxonomy.services import create_vocabulary
        from icv_taxonomy.signals import vocabulary_created

        cap = _SignalCapture()
        vocabulary_created.connect(cap, weak=False)
        try:
            vocab = create_vocabulary(name="Signal Test Vocab", slug="signal-test-vocab")
        finally:
            vocabulary_created.disconnect(cap)

        assert cap.called_once()
        assert cap.last_kwargs["vocabulary"].pk == vocab.pk

    def test_vocabulary_created_signal_not_emitted_on_update(self, db):
        """vocabulary_created is NOT emitted when an existing vocabulary is updated."""
        from icv_taxonomy.services import create_vocabulary, update_vocabulary
        from icv_taxonomy.signals import vocabulary_created

        vocab = create_vocabulary(name="Pre-existing", slug="pre-existing")

        cap = _SignalCapture()
        vocabulary_created.connect(cap, weak=False)
        try:
            update_vocabulary(vocab, description="Updated description")
        finally:
            vocabulary_created.disconnect(cap)

        assert not cap.calls


@pytest.mark.django_db
class TestVocabularyDeletedSignal:
    """Test AC-TAX-049: vocabulary_deleted emitted before vocabulary deletion."""

    def test_vocabulary_deleted_signal_emitted_on_delete(self, db):
        """vocabulary_deleted is emitted when delete_vocabulary() is called."""
        from icv_taxonomy.services import create_vocabulary, delete_vocabulary
        from icv_taxonomy.signals import vocabulary_deleted

        vocab = create_vocabulary(name="To Delete", slug="to-delete")
        vocab_pk = vocab.pk

        # Capture the vocabulary pk from inside the handler (pre-delete).
        captured_pk = []

        def handler(vocabulary, **kwargs) -> None:
            captured_pk.append(vocabulary.pk)

        vocabulary_deleted.connect(handler, weak=False)
        try:
            delete_vocabulary(vocab)
        finally:
            vocabulary_deleted.disconnect(handler)

        assert len(captured_pk) == 1
        assert captured_pk[0] == vocab_pk

    def test_vocabulary_deleted_signal_fires_before_database_delete(self, db):
        """Handler connected to vocabulary_deleted can still read the vocabulary's terms."""
        from icv_taxonomy.services import create_term, create_vocabulary, delete_vocabulary
        from icv_taxonomy.signals import vocabulary_deleted

        vocab = create_vocabulary(name="Has Terms", slug="has-terms-for-del")
        term = create_term(vocabulary=vocab, name="A Term")

        term_ids_seen = []

        def handler(vocabulary, **kwargs) -> None:
            # At pre-delete time, the terms should still be readable.
            term_ids_seen.extend(list(vocabulary.terms.values_list("pk", flat=True)))

        vocabulary_deleted.connect(handler, weak=False)
        try:
            delete_vocabulary(vocab)
        finally:
            vocabulary_deleted.disconnect(handler)

        assert term.pk in term_ids_seen


# ---------------------------------------------------------------------------
# Term lifecycle signals
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTermCreatedSignal:
    """Test AC-TAX-036: term_created emitted on term creation."""

    def test_term_created_signal_emitted_on_create(self, db, flat_vocabulary):
        """term_created is emitted when create_term() is called."""
        from icv_taxonomy.services import create_term
        from icv_taxonomy.signals import term_created

        cap = _SignalCapture()
        term_created.connect(cap, weak=False)
        try:
            term = create_term(vocabulary=flat_vocabulary, name="New Signal Term")
        finally:
            term_created.disconnect(cap)

        assert cap.called_once()
        assert cap.last_kwargs["term"].pk == term.pk
        assert cap.last_kwargs["vocabulary"].pk == flat_vocabulary.pk

    def test_term_created_signal_not_emitted_on_update(self, db, flat_vocabulary):
        """term_created is NOT emitted when an existing term is updated."""
        from icv_taxonomy.services import create_term, update_term
        from icv_taxonomy.signals import term_created

        term = create_term(vocabulary=flat_vocabulary, name="Original")

        cap = _SignalCapture()
        term_created.connect(cap, weak=False)
        try:
            update_term(term, name="Updated Name")
        finally:
            term_created.disconnect(cap)

        assert not cap.calls


@pytest.mark.django_db
class TestTermDeletedSignal:
    """Test AC-TAX-039: term_deleted emitted before term deletion (pre-delete)."""

    def test_term_deleted_signal_emitted_on_delete(self, db, flat_vocabulary):
        """term_deleted is emitted when delete_term() is called."""
        from icv_taxonomy.services import create_term, delete_term
        from icv_taxonomy.signals import term_deleted

        term = create_term(vocabulary=flat_vocabulary, name="Doomed Term")
        term_pk = term.pk
        vocab_pk = flat_vocabulary.pk

        # Capture pk values inside the handler (pre-delete, so pk is still valid).
        captured = {}

        def handler(term, vocabulary, **kwargs) -> None:
            captured["term_pk"] = term.pk
            captured["vocabulary_pk"] = vocabulary.pk

        term_deleted.connect(handler, weak=False)
        try:
            delete_term(term)
        finally:
            term_deleted.disconnect(handler)

        assert captured.get("term_pk") == term_pk
        assert captured.get("vocabulary_pk") == vocab_pk

    def test_term_deleted_signal_fires_before_database_delete(self, db, flat_vocabulary, article):
        """Handler can still read term's associations at term_deleted signal time."""
        from icv_taxonomy.services import create_term, delete_term, tag_object
        from icv_taxonomy.signals import term_deleted

        term = create_term(vocabulary=flat_vocabulary, name="Tagged Doomed Term")
        tag_object(term, article)

        association_ids_seen = []

        def handler(term, **kwargs) -> None:
            association_ids_seen.extend(list(term.associations.values_list("pk", flat=True)))

        term_deleted.connect(handler, weak=False)
        try:
            delete_term(term)
        finally:
            term_deleted.disconnect(handler)

        # At pre-delete time, associations were still readable.
        assert len(association_ids_seen) >= 1


@pytest.mark.django_db(transaction=True)
class TestTermMovedSignal:
    """Test AC-TAX-037: term_moved emitted on move via icv-tree bridge."""

    def test_term_moved_signal_emitted_on_move(self, db, hierarchical_vocabulary):
        """term_moved is emitted when move_term() is called."""
        from icv_taxonomy.services import create_term, move_term
        from icv_taxonomy.signals import term_moved

        root = hierarchical_vocabulary.terms.filter(depth=0).first()
        child = root.get_children().first()

        # Create another root-level term to move the child to.
        another_root = create_term(
            vocabulary=hierarchical_vocabulary,
            name="Another Root",
            slug="another-root",
        )

        cap = _SignalCapture()
        term_moved.connect(cap, weak=False)
        try:
            move_term(child, another_root, "last-child")
        finally:
            term_moved.disconnect(cap)

        assert cap.called_once()
        assert cap.last_kwargs["term"].pk == child.pk
        assert cap.last_kwargs["new_parent"].pk == another_root.pk


@pytest.mark.django_db(transaction=True)
class TestTermMergedSignal:
    """Test AC-TAX-038: term_merged emitted on merge."""

    def test_term_merged_signal_emitted_on_merge(self, db, flat_vocabulary, article):
        """term_merged is emitted when merge_terms() is called."""
        from icv_taxonomy.services import merge_terms, tag_object
        from icv_taxonomy.signals import term_merged

        terms = list(flat_vocabulary.terms.all()[:2])
        source, target = terms[0], terms[1]
        tag_object(source, article)

        cap = _SignalCapture()
        term_merged.connect(cap, weak=False)
        try:
            merge_terms(source, target)
        finally:
            term_merged.disconnect(cap)

        assert cap.called_once()
        assert cap.last_kwargs["source"].pk == source.pk
        assert cap.last_kwargs["target"].pk == target.pk
        assert "associations_transferred" in cap.last_kwargs


# ---------------------------------------------------------------------------
# Tagging signals
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestObjectTaggedSignal:
    """Test AC-TAX-040: object_tagged emitted on tag_object."""

    def test_object_tagged_signal_emitted_on_tag(self, db, flat_vocabulary, article):
        """object_tagged is emitted when tag_object() is called."""
        from icv_taxonomy.services import tag_object
        from icv_taxonomy.signals import object_tagged

        term = flat_vocabulary.terms.first()

        cap = _SignalCapture()
        object_tagged.connect(cap, weak=False)
        try:
            tag_object(term, article)
        finally:
            object_tagged.disconnect(cap)

        assert cap.called_once()
        assert cap.last_kwargs["term"].pk == term.pk
        assert cap.last_kwargs["content_object"] == article
        assert cap.last_kwargs["object_id"] == str(article.pk)

    def test_object_tagged_signal_includes_content_type(self, db, flat_vocabulary, article):
        """object_tagged payload includes the ContentType of the tagged object."""
        from django.contrib.contenttypes.models import ContentType

        from icv_taxonomy.services import tag_object
        from icv_taxonomy.signals import object_tagged

        term = flat_vocabulary.terms.first()
        expected_ct = ContentType.objects.get_for_model(article)

        cap = _SignalCapture()
        object_tagged.connect(cap, weak=False)
        try:
            tag_object(term, article)
        finally:
            object_tagged.disconnect(cap)

        assert cap.last_kwargs["content_type"].pk == expected_ct.pk


@pytest.mark.django_db
class TestObjectUntaggedSignal:
    """Test AC-TAX-041: object_untagged emitted on untag_object."""

    def test_object_untagged_signal_emitted_on_untag(self, db, flat_vocabulary, article):
        """object_untagged is emitted when untag_object() is called."""
        from icv_taxonomy.services import tag_object, untag_object
        from icv_taxonomy.signals import object_untagged

        term = flat_vocabulary.terms.first()
        tag_object(term, article)

        cap = _SignalCapture()
        object_untagged.connect(cap, weak=False)
        try:
            untag_object(term, article)
        finally:
            object_untagged.disconnect(cap)

        assert cap.called_once()
        assert cap.last_kwargs["term"].pk == term.pk
        assert cap.last_kwargs["content_object"] == article
