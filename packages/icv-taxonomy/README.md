# django-icv-taxonomy

[![CI](https://github.com/nigelcopley/icv-oss/actions/workflows/ci.yml/badge.svg)](https://github.com/nigelcopley/icv-oss/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/django-icv-taxonomy.svg)](https://pypi.org/project/django-icv-taxonomy/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-icv-taxonomy.svg)](https://pypi.org/project/django-icv-taxonomy/)
[![Django versions](https://img.shields.io/pypi/djversions/django-icv-taxonomy.svg)](https://pypi.org/project/django-icv-taxonomy/)
[![Licence: MIT](https://img.shields.io/badge/Licence-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Cross-domain taxonomy, vocabularies, and tagging for Django — hierarchical and flat term trees, generic object tagging, typed M2M join tables, and SKOS-style term relationships.

---

## Why Does This Exist?

Most Django projects invent their own tagging and categorisation from scratch. The result is a different pattern per app: one uses a `CharField`, another a flat M2M, a third builds a category tree — and none of them talk to each other.

django-icv-taxonomy provides a single, shared layer. One `Vocabulary` represents "Genres", another represents "Topics", another "Tags". Any model in any app can be associated with terms from any vocabulary, via a single generic association table or a typed M2M join table for high-throughput paths. Term hierarchies are powered by [django-icv-tree](https://github.com/nigelcopley/icv-oss/tree/main/packages/icv-tree) (materialised-path trees), which makes ancestor/descendant queries fast without recursive SQL.

---

## Features

### Vocabularies

- Three structural types: **flat** (simple tag lists), **hierarchical** (trees), **faceted** (multi-axis classification)
- Open or closed — closed vocabularies reject new terms; useful for controlled vocabularies
- Per-vocabulary cardinality: single-term or multi-term per object
- Optional max depth limit on hierarchical vocabularies
- Type is immutable once terms exist

### Terms

- Hierarchical tree structure via django-icv-tree (materialised paths, fast subtree queries)
- Slug unique within vocabulary, auto-generated with collision resolution
- Arbitrary JSON metadata field
- Soft deactivation without data loss
- Business-rule validation on create, update, and move

### Generic Tagging

- Tag any Django model with any term via `TermAssociation` (Django `GenericForeignKey`)
- Supports integer, UUID, and string primary keys
- Ordered associations — terms on an object carry a display order
- Cardinality enforcement for single-term vocabularies
- `cleanup_orphaned_associations()` detects and removes stale rows when tagged objects are deleted

### Typed M2M Factory

- `create_term_m2m()` generates a typed, direct-FK join table for any model
- Avoids GenericForeignKey overhead on high-read paths
- Same ordering and deduplication semantics as generic associations

### Term Relationships

- SKOS-aligned semantic links: `synonym`, `related`, `see_also`, `broader`, `narrower`
- Bidirectional types (`synonym`, `related`) automatically create the reciprocal record
- Self-relationships forbidden

### Term Lifecycle

- `merge_terms()` transfers associations, relationships, and optionally re-parents children — atomic, with `on_commit` signal
- `move_term()` delegates to icv-tree's `move_to()` service; emits `term_moved`
- Import/export: JSON-serialisable round-trip, idempotent by slug

### Developer Experience

- Swappable `Vocabulary` and `Term` models (`ICV_TAXONOMY_VOCABULARY_MODEL` / `ICV_TAXONOMY_TERM_MODEL`)
- Optional integration with `django-icv-core` (`BaseModel` — UUID PK, timestamps)
- System checks validate settings at startup
- Django signals for every lifecycle event — vocabulary, term, and tagging

---

## Requirements

- Python 3.11+
- Django 5.1+
- [django-icv-tree](https://github.com/nigelcopley/icv-oss/tree/main/packages/icv-tree) >= 0.1.0
- `django.contrib.contenttypes` (for generic tagging)

Optional:

- `django-icv-core` — adds UUID primary keys and `created_at`/`updated_at` timestamps to vocabulary and term models

---

## Installation

```bash
pip install django-icv-taxonomy
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    "django.contrib.contenttypes",  # required for generic tagging
    "icv_tree",
    "icv_taxonomy",
    ...
]
```

Run migrations:

```bash
python manage.py migrate
```

---

## Quick Start

### 1. Create a vocabulary

```python
from icv_taxonomy.services import create_vocabulary, create_term

# A flat tag vocabulary — open, multi-term per object
tags = create_vocabulary(name="Tags", vocabulary_type="flat")

# A hierarchical category tree — open, single category per object
categories = create_vocabulary(
    name="Categories",
    vocabulary_type="hierarchical",
    allow_multiple=False,
)
```

### 2. Add terms

```python
# Flat vocabulary — no parent
python_tag = create_term(vocabulary=tags, name="Python")
django_tag = create_term(vocabulary=tags, name="Django")

# Hierarchical vocabulary — nested
tech = create_term(vocabulary=categories, name="Technology")
web = create_term(vocabulary=categories, name="Web Development", parent=tech)
backend = create_term(vocabulary=categories, name="Backend", parent=web)
```

### 3. Tag objects

```python
from icv_taxonomy.services import tag_object, get_terms_for_object, untag_object

article = Article.objects.get(pk=1)

tag_object(python_tag, article)
tag_object(django_tag, article)
tag_object(backend, article)

# Retrieve all terms on the article
terms = get_terms_for_object(article)

# Retrieve only terms from a specific vocabulary
category_terms = get_terms_for_object(article, vocabulary_slug="categories")

# Remove a tag
untag_object(python_tag, article)
```

### 4. Query objects by term

```python
from icv_taxonomy.services import get_objects_for_term

# Returns a typed QuerySet of Article
articles = get_objects_for_term(django_tag, model_class=Article)

# Returns a heterogeneous list across all model types
all_tagged = get_objects_for_term(django_tag)
```

---

## Vocabulary Types

| Type | Constraint | Use Case |
|------|-----------|----------|
| `flat` | Terms must be root-level (no parent) | Tags, keywords, simple lists |
| `hierarchical` | Terms form a tree; depth optionally limited | Category trees, navigation, taxonomies |
| `faceted` | Multi-root tree; no structural restriction | Multi-axis classification (colour + size + material) |

```python
# Flat — terms are root-level only
colours = create_vocabulary(name="Colours", vocabulary_type="flat")

# Hierarchical with a depth limit
locations = create_vocabulary(
    name="Locations",
    vocabulary_type="hierarchical",
    max_depth=2,  # continent → country → region, no deeper
)

# Faceted — unrestricted structure, multiple classification axes
attributes = create_vocabulary(name="Attributes", vocabulary_type="faceted")
```

---

## Typed M2M Join Tables

For models that are tagged at high volume, the `GenericForeignKey` path can add overhead. `create_term_m2m()` generates a typed join table with direct FK joins.

```python
# In your app's models.py
from django.db import models
from icv_taxonomy.models import create_term_m2m

class Article(models.Model):
    title = models.CharField(max_length=255)

# Generate an abstract join model, then make it concrete
ArticleTermBase = create_term_m2m(Article, related_name="article_terms")

class ArticleTerm(ArticleTermBase):
    class Meta(ArticleTermBase.Meta):
        app_label = "blog"
        db_table = "blog_articleterm"
```

Query via the typed through model:

```python
from icv_taxonomy.services import get_terms_for_object_typed

terms = get_terms_for_object_typed(article, through_model=ArticleTerm)
terms_in_vocab = get_terms_for_object_typed(article, through_model=ArticleTerm, vocabulary=tags)
```

---

## Term Relationships

```python
from icv_taxonomy.services import add_relationship, remove_relationship, get_related_terms, get_synonyms

# Synonym — bidirectional; creates both directions automatically
add_relationship(python_tag, py_tag, "synonym")

# Hierarchical semantic links
add_relationship(django_tag, python_tag, "broader")
add_relationship(python_tag, django_tag, "narrower")

# Related — also bidirectional
add_relationship(django_tag, flask_tag, "related")

# See also — directional only
add_relationship(django_tag, drf_tag, "see_also")

# Query relationships
related = get_related_terms(django_tag)                       # all outgoing
narrower = get_related_terms(django_tag, "narrower")          # filtered
synonyms = get_synonyms(python_tag)                           # shortcut

# Remove
remove_relationship(django_tag, flask_tag, "related")         # removes both directions
```

---

## Term Lifecycle

### Merge terms

Transfer all associations and relationships from one term to another, then deactivate the source. Wrapped in `transaction.atomic`.

```python
from icv_taxonomy.services import merge_terms

result = merge_terms(source=old_term, target=new_term)
# result = {"associations_transferred": 42, "relationships_transferred": 5, "children_reparented": 0}

# Source has children — re-parent them to target before merging
result = merge_terms(source=old_term, target=new_term, children_strategy="reparent")

# Re-parent children up to source's parent instead
result = merge_terms(source=old_term, target=new_term, children_strategy="reparent_up")
```

### Move terms

```python
from icv_taxonomy.services import move_term

# Move term and its entire subtree under a new parent
move_term(term=backend, target=api, position="last-child")

# Position options: "first-child", "last-child", "left", "right"
```

### Deactivate without deleting

```python
from icv_taxonomy.services import deactivate_term

deactivate_term(old_tag)
# is_active=False; existing associations are preserved
# Inactive terms cannot be used for new tagging operations
```

---

## Import and Export

Round-trip a vocabulary and all its terms and relationships as a JSON-serialisable dict.

```python
from icv_taxonomy.services import export_vocabulary, import_vocabulary

# Export
data = export_vocabulary(categories)
data = export_vocabulary(categories, include_inactive=True)

# Import — creates vocabulary if slug absent, updates if present (idempotent)
result = import_vocabulary(data)
# result = {"created": 12, "updated": 3, "skipped": 0}

# Import into an existing vocabulary
result = import_vocabulary(data, vocabulary=existing_vocab)
```

The export format:

```json
{
  "name": "Categories",
  "slug": "categories",
  "vocabulary_type": "hierarchical",
  "is_open": true,
  "allow_multiple": false,
  "max_depth": null,
  "terms": [
    {"name": "Technology", "slug": "technology", "parent_slug": null, "is_active": true},
    {"name": "Web Development", "slug": "web-development", "parent_slug": "technology", "is_active": true}
  ],
  "relationships": []
}
```

---

## Bulk Tagging

```python
from icv_taxonomy.services import bulk_tag_objects

articles = list(Article.objects.filter(topic="python"))
bulk_tag_objects(python_tag, articles)

# Suppress signals for large batches (caller handles downstream updates)
bulk_tag_objects(python_tag, articles, emit_signals=False)
```

---

## Orphan Cleanup

Generic FK associations have no database-level cascade. When a tagged object is deleted, its `TermAssociation` rows persist. Clean them up with:

```python
from icv_taxonomy.services import cleanup_orphaned_associations

# Check all content types
result = cleanup_orphaned_associations()
# result = {"checked": 500, "orphaned": 12, "removed": 12}

# Restrict to a single model
result = cleanup_orphaned_associations(model_class=Article)

# Dry run — report without deleting
result = cleanup_orphaned_associations(dry_run=True)
```

---

## Models Reference

### Vocabulary

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | CharField(255) | — | Human-readable name. Globally unique. |
| `slug` | SlugField(255) | auto | URL-safe identifier. Auto-generated from name if blank. |
| `description` | TextField | `""` | Optional description of the vocabulary's purpose. |
| `vocabulary_type` | CharField | `"flat"` | One of `flat`, `hierarchical`, `faceted`. Immutable once terms exist. |
| `is_open` | BooleanField | `True` | When False, no new terms may be added. |
| `allow_multiple` | BooleanField | `True` | When False, each object may have at most one term from this vocabulary. |
| `max_depth` | PositiveIntegerField | `None` | Maximum term depth (zero-based). Null = unlimited. |
| `metadata` | JSONField | `{}` | Arbitrary key/value pairs. |
| `is_active` | BooleanField | `True` | Inactive vocabularies are hidden from default querysets. |

**Managers:** `objects` (active only) · `all_objects` (unfiltered)

### Term

Extends `icv_tree.TreeNode` — inherits `path`, `depth`, `order`, `parent`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vocabulary` | ForeignKey | — | The vocabulary this term belongs to. Immutable after creation. |
| `name` | CharField(255) | — | Human-readable label. |
| `slug` | SlugField(255) | auto | URL-safe identifier, unique within vocabulary. Auto-generated from name if blank. |
| `description` | TextField | `""` | Optional description. |
| `is_active` | BooleanField | `True` | Inactive terms are hidden from default querysets and blocked from new tagging. |
| `metadata` | JSONField | `{}` | Arbitrary key/value pairs. |
| `path` | (from TreeNode) | — | Materialised path string. |
| `depth` | (from TreeNode) | — | Zero-based depth in tree. |
| `parent` | (from TreeNode) | `None` | Parent term, or None for root terms. |

**Managers:** `objects` (active only, tree-aware) · `all_objects` (unfiltered tree manager)

**TreeQuerySet methods** (inherited from icv-tree):

```python
Term.objects.active()                        # active terms only
Term.objects.descendants_of(term)            # all descendants
Term.objects.ancestors_of(term)              # all ancestors
Term.objects.children_of(term)               # direct children
Term.objects.roots()                         # root-level terms
```

### TermRelationship

| Field | Type | Description |
|-------|------|-------------|
| `term_from` | ForeignKey(Term) | Source term. |
| `term_to` | ForeignKey(Term) | Target term. |
| `relationship_type` | CharField | One of `synonym`, `related`, `see_also`, `broader`, `narrower`. |
| `metadata` | JSONField | Arbitrary key/value pairs. |

Unique together: `(term_from, term_to, relationship_type)`.

### TermAssociation

| Field | Type | Description |
|-------|------|-------------|
| `term` | ForeignKey(Term) | The term applied as a tag. |
| `content_type` | ForeignKey(ContentType) | Content type of the tagged object. |
| `object_id` | CharField(255) | PK of the tagged object (stored as string; supports int, UUID, and other types). |
| `content_object` | GenericForeignKey | Resolved reference to the tagged object. |
| `order` | PositiveIntegerField | Display order among this object's term associations. |
| `created_at` | DateTimeField | Timestamp when the association was created. |

Unique together: `(term, content_type, object_id)`.

---

## Services Reference

All public functions are importable from `icv_taxonomy.services`.

### Vocabulary Management

| Function | Description |
|----------|-------------|
| `create_vocabulary(name, slug="", vocabulary_type="flat", **kwargs)` | Create a new vocabulary. Slug auto-generated with collision resolution. |
| `update_vocabulary(vocabulary, **kwargs)` | Update mutable fields. Guards against type change when terms exist. |
| `delete_vocabulary(vocabulary)` | Delete a vocabulary and all cascaded terms and associations. |

### Term Management

| Function | Description |
|----------|-------------|
| `create_term(vocabulary, name, slug="", parent=None, **kwargs)` | Create a term. Validates closed vocabulary, flat constraint, max depth, vocabulary boundary. |
| `update_term(term, **kwargs)` | Update mutable term fields. Guards against vocabulary change. |
| `move_term(term, target, position="last-child")` | Move term and subtree. Position: `first-child`, `last-child`, `left`, `right`. |
| `merge_terms(source, target, children_strategy="refuse")` | Merge source into target. Strategies: `refuse`, `reparent`, `reparent_up`. Returns counts dict. |
| `deactivate_term(term)` | Set `is_active=False`. Preserves existing associations. |
| `delete_term(term)` | Hard-delete term and all cascaded descendants, associations, and relationships. |

### Tagging

| Function | Description |
|----------|-------------|
| `tag_object(term, obj)` | Associate a term with an object. Validates activity, uniqueness, cardinality. |
| `untag_object(term, obj)` | Remove a term from an object. |
| `replace_term_on_object(obj, old_term, new_term)` | Atomic swap — untag old, tag new. |
| `bulk_tag_objects(term, objects, emit_signals=True)` | Tag a list of objects in bulk via `bulk_create`. Skips duplicates. |
| `get_terms_for_object(obj, vocabulary=None, vocabulary_slug=None)` | QuerySet of terms on an object, optionally filtered by vocabulary. |
| `get_objects_for_term(term, model_class=None)` | Typed QuerySet (if `model_class` given) or heterogeneous list of tagged objects. |
| `get_terms_for_object_typed(obj, through_model, vocabulary=None)` | Terms via typed M2M through table — no GenericFK overhead. |
| `cleanup_orphaned_associations(model_class=None, dry_run=False)` | Remove associations whose objects no longer exist. Returns counts dict. |

### Term Relationships

| Function | Description |
|----------|-------------|
| `add_relationship(term_from, term_to, relationship_type)` | Create a typed relationship. Bidirectional types create both directions. |
| `remove_relationship(term_from, term_to, relationship_type)` | Remove a relationship. Bidirectional types remove both directions. |
| `get_related_terms(term, relationship_type=None)` | QuerySet of terms on the outgoing side of matching relationships. |
| `get_synonyms(term)` | Shortcut for `get_related_terms(term, "synonym")`. |

### Import / Export

| Function | Description |
|----------|-------------|
| `export_vocabulary(vocabulary, include_inactive=False)` | Serialise vocabulary and terms to a JSON-serialisable dict. |
| `import_vocabulary(data, vocabulary=None)` | Import from dict. Idempotent by slug. Returns `{"created", "updated", "skipped"}`. |

---

## Settings Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `ICV_TAXONOMY_VOCABULARY_MODEL` | `"icv_taxonomy.Vocabulary"` | Swappable vocabulary model. Dotted `app_label.ModelName`. |
| `ICV_TAXONOMY_TERM_MODEL` | `"icv_taxonomy.Term"` | Swappable term model. Dotted `app_label.ModelName`. |
| `ICV_TAXONOMY_AUTO_SLUG` | `True` | Auto-generate slug from name when blank on save. |
| `ICV_TAXONOMY_SLUG_MAX_LENGTH` | `255` | Maximum length for auto-generated slugs. |
| `ICV_TAXONOMY_CASE_SENSITIVE_SLUGS` | `False` | When False, slugs are lowercased on save. |
| `ICV_TAXONOMY_ENFORCE_VOCABULARY_TYPE` | `True` | When True, flat vocabulary terms must be root-level. Set to False for migration compatibility. |

---

## Swappable Models

Point `ICV_TAXONOMY_VOCABULARY_MODEL` and `ICV_TAXONOMY_TERM_MODEL` to your own subclasses to add project-specific fields.

```python
# myapp/models.py
from icv_taxonomy.models import AbstractVocabulary, AbstractTerm

class ProjectVocabulary(AbstractVocabulary):
    owner = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True)

    class Meta(AbstractVocabulary.Meta):
        abstract = False
        db_table = "myapp_vocabulary"

class ProjectTerm(AbstractTerm):
    icon = models.CharField(max_length=50, blank=True)
    colour = models.CharField(max_length=7, blank=True)

    class Meta(AbstractTerm.Meta):
        abstract = False
        db_table = "myapp_term"
```

```python
# settings.py
ICV_TAXONOMY_VOCABULARY_MODEL = "myapp.ProjectVocabulary"
ICV_TAXONOMY_TERM_MODEL = "myapp.ProjectTerm"
```

---

## Admin Integration

`VocabularyAdmin` and `TermAdmin` are registered automatically. No additional configuration is required.

**VocabularyAdmin** provides:

- List display with active term count (annotated, sortable)
- Filters by `vocabulary_type`, `is_open`, and `is_active`
- Grouped fieldsets: General, Configuration, Metadata, Timestamps

**TermAdmin** provides:

- Indented title column showing tree depth (via `icv_tree.admin.TreeAdmin`)
- Filters by vocabulary, active status, and depth
- `TermRelationshipInline` for managing relationships directly on the term form
- Read-only path, depth, and order fields
- Grouped fieldsets: General, Tree, Metadata, Timestamps

To register against a custom admin site or use the classes directly:

```python
from icv_taxonomy.admin import VocabularyAdmin, TermAdmin
from icv_taxonomy.conf import get_vocabulary_model, get_term_model

my_admin_site.register(get_vocabulary_model(), VocabularyAdmin)
my_admin_site.register(get_term_model(), TermAdmin)
```

---

## Signals Reference

Connect to these signals from consuming apps to react to taxonomy events (cache invalidation, search re-indexing, audit logging).

```python
from icv_taxonomy import signals

@receiver(signals.object_tagged)
def handle_tagged(sender, term, content_object, content_type, object_id, **kwargs):
    search_index.update(content_object)
```

| Signal | Keyword Arguments | Fired When |
|--------|------------------|------------|
| `vocabulary_created` | `vocabulary` | After a new vocabulary is created |
| `vocabulary_deleted` | `vocabulary` | Before a vocabulary is deleted |
| `term_created` | `term`, `vocabulary` | After a new term is created |
| `term_moved` | `term`, `old_parent`, `new_parent`, `old_path` | After a term is moved in the tree |
| `term_merged` | `source`, `target`, `associations_transferred`, `children_reparented` | After a merge completes (on commit) |
| `term_deleted` | `term`, `vocabulary` | Before a term is deleted |
| `object_tagged` | `term`, `content_object`, `content_type`, `object_id` | After a term is applied to an object |
| `object_untagged` | `term`, `content_object`, `content_type`, `object_id` | After a term is removed from an object |

---

## System Checks

| ID | Severity | Condition |
|----|----------|-----------|
| `icv_taxonomy.E001` | Error | `ICV_TAXONOMY_VOCABULARY_MODEL` is not a valid dotted `app_label.ModelName` string |
| `icv_taxonomy.E002` | Error | `ICV_TAXONOMY_TERM_MODEL` is not a valid dotted `app_label.ModelName` string |

---

## Testing

### Fixtures

The conftest at `packages/icv-taxonomy/tests/conftest.py` provides reusable pytest fixtures:

```python
# Available fixtures
flat_vocabulary       # flat vocab with 5 active terms
hierarchical_vocabulary  # 3-level tree (root → 3 children → 6 grandchildren)
closed_vocabulary     # flat vocab with is_open=False, 3 terms
single_term_vocabulary   # flat vocab with allow_multiple=False, 3 terms
article               # persisted Article instance
product               # persisted Product instance
tagged_article        # article tagged with the first term from flat_vocabulary
```

### Writing tests

```python
import pytest
from icv_taxonomy.services import create_vocabulary, create_term, tag_object, get_terms_for_object

@pytest.mark.django_db
def test_tag_round_trip(article):
    vocab = create_vocabulary(name="Topics", vocabulary_type="flat")
    python = create_term(vocabulary=vocab, name="Python")

    tag_object(python, article)

    terms = get_terms_for_object(article)
    assert list(terms) == [python]


@pytest.mark.django_db
def test_single_term_cardinality(single_term_vocabulary, article):
    from icv_taxonomy.exceptions import TaxonomyValidationError

    terms = list(single_term_vocabulary.terms.all())
    tag_object(terms[0], article)

    with pytest.raises(TaxonomyValidationError):
        tag_object(terms[1], article)
```

### Settings for test suites

```python
# tests/settings.py
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "icv_tree",
    "icv_taxonomy",
]

ICV_TAXONOMY_AUTO_SLUG = True
ICV_TAXONOMY_CASE_SENSITIVE_SLUGS = False
ICV_TAXONOMY_ENFORCE_VOCABULARY_TYPE = True

# icv-tree settings
ICV_TREE_PATH_SEPARATOR = "/"
ICV_TREE_STEP_LENGTH = 4
ICV_TREE_MAX_PATH_LENGTH = 255
ICV_TREE_ENABLE_CTE = False
```

---

## Licence

MIT
