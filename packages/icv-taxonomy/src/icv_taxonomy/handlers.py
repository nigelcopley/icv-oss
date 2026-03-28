"""Signal handlers for icv-taxonomy.

Connected in IcvTaxonomyConfig.ready() via import.

handle_vocabulary_post_save  — emits vocabulary_created on new Vocabulary instances.
handle_vocabulary_pre_delete — emits vocabulary_deleted before a Vocabulary is removed.
handle_term_post_save        — emits term_created on new Term instances.
handle_term_pre_delete       — emits term_deleted before a Term is removed.
handle_node_moved            — bridges icv_tree.signals.node_moved → term_moved when
                               the moved node is a Term subclass.
"""

from __future__ import annotations

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_vocabulary_subclass(sender) -> bool:  # type: ignore[no-untyped-def]
    """Return True if sender is a concrete (non-abstract) Vocabulary subclass."""
    from .conf import get_vocabulary_model

    Vocabulary = get_vocabulary_model()
    return isinstance(sender, type) and issubclass(sender, Vocabulary) and not sender._meta.abstract


def _is_term_subclass(sender) -> bool:  # type: ignore[no-untyped-def]
    """Return True if sender is a concrete (non-abstract) Term subclass."""
    from .conf import get_term_model

    Term = get_term_model()
    return isinstance(sender, type) and issubclass(sender, Term) and not sender._meta.abstract


# ---------------------------------------------------------------------------
# Vocabulary handlers
# ---------------------------------------------------------------------------


@receiver(post_save)
def handle_vocabulary_post_save(  # type: ignore[no-untyped-def]
    sender, instance, created, **kwargs
) -> None:
    """Emit vocabulary_created when a new Vocabulary instance is saved.

    Ignores updates (created=False) and non-Vocabulary senders.
    """
    if not _is_vocabulary_subclass(sender):
        return
    if not created:
        return

    from .signals import vocabulary_created

    vocabulary_created.send(sender=sender, vocabulary=instance)


@receiver(pre_delete)
def handle_vocabulary_pre_delete(  # type: ignore[no-untyped-def]
    sender, instance, **kwargs
) -> None:
    """Emit vocabulary_deleted before a Vocabulary instance is removed.

    Fires pre-delete so handlers can still inspect the vocabulary's terms
    before the CASCADE removes them.
    """
    if not _is_vocabulary_subclass(sender):
        return

    from .signals import vocabulary_deleted

    vocabulary_deleted.send(sender=sender, vocabulary=instance)


# ---------------------------------------------------------------------------
# Term handlers
# ---------------------------------------------------------------------------


@receiver(post_save)
def handle_term_post_save(  # type: ignore[no-untyped-def]
    sender, instance, created, **kwargs
) -> None:
    """Emit term_created when a new Term instance is saved.

    Ignores updates (created=False) and non-Term senders.
    """
    if not _is_term_subclass(sender):
        return
    if not created:
        return

    from .signals import term_created

    term_created.send(sender=sender, term=instance, vocabulary=instance.vocabulary)


@receiver(pre_delete)
def handle_term_pre_delete(  # type: ignore[no-untyped-def]
    sender, instance, **kwargs
) -> None:
    """Emit term_deleted before a Term instance is removed.

    Fires pre-delete so handlers can still inspect the term's associations
    (e.g. TermAssociation rows) before the CASCADE removes them.
    """
    if not _is_term_subclass(sender):
        return

    from .signals import term_deleted

    term_deleted.send(sender=sender, term=instance, vocabulary=instance.vocabulary)


# ---------------------------------------------------------------------------
# icv-tree bridge: node_moved → term_moved
# ---------------------------------------------------------------------------


def _connect_node_moved_handler() -> None:
    """Connect handle_node_moved to icv_tree.signals.node_moved if icv-tree is installed.

    Called from IcvTaxonomyConfig.ready(). Wrapped in a function so that the
    import of icv_tree.signals is deferred until Django's app registry is ready,
    and so the handler is silently skipped when icv-tree is not installed (e.g.
    in consuming projects that use flat vocabularies only).
    """
    try:
        from icv_tree import signals as tree_signals
    except ImportError:
        # icv-tree is not installed — term_moved will only be emitted by the
        # merge service directly; the tree bridge is not available.
        return

    tree_signals.node_moved.connect(
        handle_node_moved,
        dispatch_uid="icv_taxonomy.handlers.handle_node_moved",
    )


def handle_node_moved(  # type: ignore[no-untyped-def]
    sender, instance, old_parent, new_parent, old_path, **kwargs
) -> None:
    """Bridge icv_tree.signals.node_moved to icv_taxonomy.signals.term_moved.

    Only emits term_moved when the moved node's model is a concrete Term
    subclass. Passes taxonomy-specific context (term, old_parent, new_parent,
    old_path) rather than the raw tree fields.

    Connected via _connect_node_moved_handler() in IcvTaxonomyConfig.ready().
    """
    if not _is_term_subclass(sender):
        return

    from .signals import term_moved

    term_moved.send(
        sender=sender,
        term=instance,
        old_parent=old_parent,
        new_parent=new_parent,
        old_path=old_path,
    )
