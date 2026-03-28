"""Signal definitions for icv-taxonomy.

Consuming projects connect to these signals to react to taxonomy lifecycle
events (e.g., search re-indexing, cache invalidation).
"""

from __future__ import annotations

from django.dispatch import Signal

# ---------------------------------------------------------------------------
# Vocabulary lifecycle
# ---------------------------------------------------------------------------

# Emitted after a new Vocabulary instance is created.
#
# Keyword arguments:
#   sender      — The concrete Vocabulary model class
#   vocabulary  — The newly created Vocabulary instance
vocabulary_created = Signal()

# Emitted before a Vocabulary instance is deleted (pre-delete so handlers
# can still read the vocabulary's terms before CASCADE removes them).
#
# Keyword arguments:
#   sender      — The concrete Vocabulary model class
#   vocabulary  — The Vocabulary instance about to be deleted
vocabulary_deleted = Signal()

# ---------------------------------------------------------------------------
# Term lifecycle
# ---------------------------------------------------------------------------

# Emitted after a new Term instance is created.
#
# Keyword arguments:
#   sender      — The concrete Term model class
#   term        — The newly created Term instance
#   vocabulary  — The Vocabulary instance the term belongs to (instance.vocabulary)
term_created = Signal()

# Emitted after a Term has been moved to a new position in the tree
# (i.e. its parent changed, as signalled by icv_tree.signals.node_moved).
#
# Keyword arguments:
#   sender      — The concrete Term model class
#   term        — The Term instance after the move (new parent/path already set)
#   old_parent  — The parent Term (or None) before the move
#   new_parent  — The parent Term (or None) after the move
#   old_path    — str, the term's materialised path value before the move
term_moved = Signal()

# Emitted after two terms have been merged via the merge service.
#
# Keyword arguments:
#   sender                  — The concrete Term model class
#   source                  — The source Term instance (now deleted)
#   target                  — The target Term instance (associations transferred to)
#   associations_transferred — int, count of TermAssociation rows re-pointed to target
#   children_reparented     — int, count of child terms re-parented to target
term_merged = Signal()

# Emitted before a Term instance is deleted (pre-delete so handlers can still
# read the term's associations before CASCADE removes them).
#
# Keyword arguments:
#   sender      — The concrete Term model class
#   term        — The Term instance about to be deleted
#   vocabulary  — The Vocabulary instance the term belongs to (instance.vocabulary)
term_deleted = Signal()

# ---------------------------------------------------------------------------
# Tagging lifecycle
# ---------------------------------------------------------------------------

# Emitted after a content object has been tagged with a term.
#
# Keyword arguments:
#   sender          — The concrete Term model class
#   term            — The Term instance applied as a tag
#   content_object  — The tagged object (GenericForeignKey target)
#   content_type    — The ContentType instance for the tagged object
#   object_id       — The PK of the tagged object (as stored on TermAssociation)
object_tagged = Signal()

# Emitted after a tag has been removed from a content object.
#
# Keyword arguments:
#   sender          — The concrete Term model class
#   term            — The Term instance removed as a tag
#   content_object  — The untagged object (GenericForeignKey target)
#   content_type    — The ContentType instance for the untagged object
#   object_id       — The PK of the untagged object (as stored on TermAssociation)
object_untagged = Signal()
