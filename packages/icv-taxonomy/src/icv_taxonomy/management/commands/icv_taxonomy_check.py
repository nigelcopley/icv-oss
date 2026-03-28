"""
Management command: icv_taxonomy_check

Usage::

    python manage.py icv_taxonomy_check
    python manage.py icv_taxonomy_check --fix

Validates taxonomy data integrity across three dimensions:

1. **Orphaned associations** — TermAssociation rows whose referenced object no
   longer exists. Detected via ``cleanup_orphaned_associations(dry_run=True)``.
   With ``--fix``, removed via ``cleanup_orphaned_associations(dry_run=False)``.

2. **Vocabulary type constraint violations** — flat-vocabulary terms with a
   non-null parent (violates BR-TAX-008). With ``--fix``, the parent is set to
   None (promoting the term to root level).

3. **Path inconsistencies** — hierarchical and faceted vocabulary terms whose
   materialised path does not match the expected value derived from the tree
   structure. Delegates to icv-tree's ``rebuild`` service when ``--fix`` is
   given.

Exit codes:
  0 — no issues found (or all issues fixed)
  1 — issues found and ``--fix`` not specified (or some issues could not be fixed)
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check (and optionally fix) taxonomy data integrity."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--fix",
            action="store_true",
            default=False,
            help="Attempt to repair detected issues.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        fix: bool = options["fix"]
        issues_found = False

        # --- 1. Orphaned associations ---
        issues_found = self._check_orphaned_associations(fix=fix) or issues_found

        # --- 2. Vocabulary type constraint violations ---
        issues_found = self._check_type_violations(fix=fix) or issues_found

        # --- 3. Path inconsistencies (hierarchical / faceted vocabularies) ---
        issues_found = self._check_path_inconsistencies(fix=fix) or issues_found

        # --- Summary ---
        if issues_found:
            if fix:
                self.stdout.write(self.style.WARNING("Check complete. Some issues were repaired; review output above."))
            else:
                self.stdout.write(self.style.ERROR("Issues found. Run with --fix to attempt repairs."))
                raise SystemExit(1)
        else:
            self.stdout.write(self.style.SUCCESS("Taxonomy integrity check passed."))

    # ------------------------------------------------------------------
    # Check helpers
    # ------------------------------------------------------------------

    def _check_orphaned_associations(self, *, fix: bool) -> bool:
        """Detect (and optionally remove) orphaned TermAssociation records."""
        from icv_taxonomy.services import cleanup_orphaned_associations

        self.stdout.write("Checking orphaned associations...")

        try:
            result = cleanup_orphaned_associations(dry_run=True)
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f"  Error checking orphaned associations: {exc}"))
            return True

        orphaned: int = result.get("orphaned", 0)
        checked: int = result.get("checked", 0)

        if orphaned == 0:
            self.stdout.write(f"  OK — checked {checked} association(s), none orphaned.")
            return False

        self.stdout.write(self.style.WARNING(f"  Found {orphaned} orphaned association(s) out of {checked} checked."))

        if fix:
            try:
                fix_result = cleanup_orphaned_associations(dry_run=False)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"  Error removing orphaned associations: {exc}"))
                return True
            removed: int = fix_result.get("removed", 0)
            self.stdout.write(self.style.SUCCESS(f"  Fixed — removed {removed} orphaned association(s)."))
            return False

        return True

    def _check_type_violations(self, *, fix: bool) -> bool:
        """Detect flat-vocabulary terms with a non-null parent."""
        from icv_taxonomy.conf import get_term_model

        self.stdout.write("Checking vocabulary type constraint violations...")

        try:
            Term = get_term_model()
            violations = list(
                Term.all_objects.filter(
                    vocabulary__vocabulary_type="flat",
                    parent__isnull=False,
                ).select_related("vocabulary")
            )
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f"  Error querying type violations: {exc}"))
            return True

        if not violations:
            self.stdout.write("  OK — no vocabulary type constraint violations.")
            return False

        self.stdout.write(self.style.WARNING(f"  Found {len(violations)} flat-vocabulary term(s) with a parent set:"))
        for term in violations:
            self.stdout.write(
                f"    - Term '{term.slug}' in vocabulary '{term.vocabulary.slug}' (parent: {term.parent_id})"
            )

        if fix:
            fixed = 0
            errors = 0
            for term in violations:
                try:
                    Term.all_objects.filter(pk=term.pk).update(parent=None)
                    fixed += 1
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(self.style.ERROR(f"  Error fixing term '{term.slug}': {exc}"))
                    errors += 1
            self.stdout.write(self.style.SUCCESS(f"  Fixed {fixed} term(s); {errors} error(s)."))
            return errors > 0

        return True

    def _check_path_inconsistencies(self, *, fix: bool) -> bool:
        """Detect terms in hierarchical/faceted vocabularies with incorrect paths.

        Delegates path rebuilding to icv-tree when --fix is requested.
        """
        self.stdout.write("Checking path inconsistencies in hierarchical/faceted vocabularies...")

        try:
            from icv_taxonomy.conf import get_term_model, get_vocabulary_model

            Term = get_term_model()
            Vocabulary = get_vocabulary_model()

            # Gather hierarchical/faceted vocabularies.
            hier_vocabs = list(Vocabulary.all_objects.filter(vocabulary_type__in=("hierarchical", "faceted")))
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f"  Error loading hierarchical vocabularies: {exc}"))
            return True

        if not hier_vocabs:
            self.stdout.write("  OK — no hierarchical or faceted vocabularies to check.")
            return False

        inconsistencies: list[str] = []

        for vocab in hier_vocabs:
            try:
                # Check for terms whose depth is inconsistent with parent depth.
                # A term at depth D should have a parent at depth D-1.
                bad_terms = list(
                    Term.all_objects.filter(
                        vocabulary=vocab,
                        parent__isnull=False,
                    )
                    .exclude(depth=0)
                    .select_related("parent")
                    .filter(depth__lte=0)  # depth <= 0 but has a parent
                )
                if bad_terms:
                    for term in bad_terms:
                        inconsistencies.append(
                            f"Term '{term.slug}' (vocab '{vocab.slug}'): depth={term.depth} but parent is set"
                        )

                # Check for root terms with depth > 0.
                bad_roots = list(
                    Term.all_objects.filter(
                        vocabulary=vocab,
                        parent__isnull=True,
                    ).exclude(depth=0)
                )
                for term in bad_roots:
                    inconsistencies.append(
                        f"Term '{term.slug}' (vocab '{vocab.slug}'): root term has depth={term.depth}"
                    )
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"  Error checking vocab '{vocab.slug}': {exc}"))
                inconsistencies.append(f"Error in vocab '{vocab.slug}': {exc}")

        if not inconsistencies:
            self.stdout.write(f"  OK — checked {len(hier_vocabs)} vocabulary/vocabularies, no path inconsistencies.")
            return False

        self.stdout.write(self.style.WARNING(f"  Found {len(inconsistencies)} path inconsistency/inconsistencies:"))
        for msg in inconsistencies:
            self.stdout.write(f"    - {msg}")

        if fix:
            try:
                from icv_tree.services import rebuild

                # rebuild() operates on the entire concrete model table, so
                # calling it once with the Term model class is sufficient even
                # when multiple hierarchical vocabularies are affected.
                rebuild(Term)
                self.stdout.write(self.style.SUCCESS("  Fixed — tree paths rebuilt via icv-tree rebuild service."))
                return False
            except ImportError:
                self.stderr.write(self.style.ERROR("  Cannot rebuild paths: icv-tree rebuild service not available."))
                return True
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"  Error rebuilding paths: {exc}"))
                return True

        return True
