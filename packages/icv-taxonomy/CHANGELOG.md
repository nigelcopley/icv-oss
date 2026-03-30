# Changelog

All notable changes to django-icv-taxonomy are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
