# Changelog

All notable changes to django-icv-taxonomy are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.3.2] — 2026-04-20

### Fixed

- Standalone fallback base model now provides UUID primary key and
  `created_at`/`updated_at` timestamps (matching `icv_core.BaseModel`)
  instead of bare `models.Model`. Installing icv-taxonomy without
  django-icv-core no longer breaks the model schema.
- Admin no longer conditionally hides timestamp fields when icv-core is
  absent — timestamps are always present and always shown.

## [0.3.1] — 2026-04-18

### Fixed

- `AbstractTermRelationship` and `AbstractTermAssociation` now declare
  `id = models.BigAutoField(...)` explicitly instead of relying on
  `default_auto_field` resolution. Consumer projects with a different
  `DEFAULT_AUTO_FIELD` setting no longer get phantom `AlterField`
  migrations for these junction tables.

## [0.3.0] — 2026-04-08

Promoted to Production/Stable.

### Added

- `clear_vocabulary(vocab)` — delete all terms without deleting the
  vocabulary; single bulk DELETE with database CASCADE
- 50 new tests covering admin, management commands, template tags,
  clear_vocabulary, and signal emission

### Changed

- `merge_terms()` rewritten with bulk operations — batch duplicate
  detection, bulk UPDATE for associations/relationships, `bulk_update()`
  for child reparenting. ~1,800 queries → ~18 for a typical merge (100x).
- `import_vocabulary()` uses `bulk_update()` for existing terms instead
  of per-term `save()`. ~30,000 queries → ~100 for 10K terms (300x).
- VocabularyAdmin resolves term related_name dynamically via
  `_get_term_related_name()` instead of hardcoded `"term_set"`, fixing
  breakage with custom Term subclasses via `ICV_TAXONOMY_TERM_MODEL`.

### Fixed

- `__version__` synced with pyproject.toml (was 0.1.0, now 0.3.0)
- `%(class)s_set` related_name pattern on all ForeignKeys for swappable
  model support

## [0.2.1] — 2026-03-30

### Fixed

- Add missing `swappable` Meta attribute to concrete `Vocabulary` and `Term` models
- Add missing `swappable` option to `0001_initial` migration for both models

## [0.2.0] — 2026-03-30

### Changed

- Require Django >= 5.0; dropped Django 4.2 support
- Require Python >= 3.11
- Added Django 6.0 classifier

## [0.1.1] — 2026-03-29

### Changed

- Bumped minimum `django-icv-tree` dependency to >= 0.1.1
- Promoted Development Status to Beta

## [0.1.0] — 2026-03-27

### Added

- `AbstractVocabulary` and `AbstractTerm` abstract base models for subclassing
- Concrete `Vocabulary`, `Term`, `TermRelationship`, and `TermAssociation` models
- Swappable models via `ICV_TAXONOMY_VOCABULARY_MODEL` and `ICV_TAXONOMY_TERM_MODEL`
  settings (AUTH_USER_MODEL pattern)
- `get_vocabulary_model()` and `get_term_model()` runtime resolution functions
- `VocabularyManager` and `TaxonomyTermManager` with active-object filtering
- Service layer: vocabulary management, term management, tagging, relationships,
  import/export, and bulk operations
- `create_term_m2m()` factory for typed many-to-many relationships
- `AbstractTermAssociation` for generic tagging via Django's `GenericForeignKey`
- `AbstractTermRelationship` for SKOS-style semantic links between terms
- System checks `icv_taxonomy.E001` and `icv_taxonomy.E002` for swappable settings
  validation
- Signal handlers bridging `icv_tree.node_moved` to `taxonomy.term_moved`
- Admin integration with lazy registration for swappable models
