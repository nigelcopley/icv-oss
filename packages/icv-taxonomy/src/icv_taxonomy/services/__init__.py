"""icv-taxonomy services public API."""

from __future__ import annotations

from .import_export import export_vocabulary, import_vocabulary
from .relationships import add_relationship, get_related_terms, get_synonyms, remove_relationship
from .tagging import (
    bulk_tag_objects,
    cleanup_orphaned_associations,
    get_objects_for_term,
    get_terms_for_object,
    get_terms_for_object_typed,
    replace_term_on_object,
    tag_object,
    untag_object,
)
from .term_management import (
    create_term,
    deactivate_term,
    delete_term,
    merge_terms,
    move_term,
    update_term,
)
from .vocabulary_management import clear_vocabulary, create_vocabulary, delete_vocabulary, update_vocabulary

__all__ = [
    # vocabulary_management
    "create_vocabulary",
    "update_vocabulary",
    "delete_vocabulary",
    "clear_vocabulary",
    # term_management
    "create_term",
    "update_term",
    "move_term",
    "merge_terms",
    "delete_term",
    "deactivate_term",
    # tagging
    "tag_object",
    "untag_object",
    "get_terms_for_object",
    "get_objects_for_term",
    "replace_term_on_object",
    "bulk_tag_objects",
    "get_terms_for_object_typed",
    "cleanup_orphaned_associations",
    # relationships
    "add_relationship",
    "remove_relationship",
    "get_related_terms",
    "get_synonyms",
    # import_export
    "export_vocabulary",
    "import_vocabulary",
]
