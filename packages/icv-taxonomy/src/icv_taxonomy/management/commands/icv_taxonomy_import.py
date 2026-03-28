"""
Management command: icv_taxonomy_import

Usage::

    python manage.py icv_taxonomy_import <file_path>
    python manage.py icv_taxonomy_import <file_path> --vocabulary <slug>
    python manage.py icv_taxonomy_import <file_path> --dry-run

Reads a JSON file produced by ``icv_taxonomy_export`` and calls the
``import_vocabulary`` service to create or update the vocabulary and its terms.

With ``--vocabulary``, imports terms into an existing vocabulary identified by
slug rather than creating a new one from the file.

With ``--dry-run``, reports what would change without writing anything to the
database.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Import a vocabulary from a JSON file."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "file_path",
            type=str,
            help="Path to the JSON file to import.",
        )
        parser.add_argument(
            "--vocabulary",
            type=str,
            default=None,
            metavar="SLUG",
            help=(
                "Slug of an existing vocabulary to import into. If omitted, the vocabulary is created from the file."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report what would change without writing to the database.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        file_path = Path(options["file_path"])
        vocabulary_slug: str | None = options["vocabulary"]
        dry_run: bool = options["dry_run"]

        # --- Read file ---

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {file_path}: {exc}") from exc

        # --- Resolve target vocabulary (when --vocabulary is provided) ---

        vocabulary = None
        if vocabulary_slug is not None:
            from icv_taxonomy.conf import get_vocabulary_model

            Vocabulary = get_vocabulary_model()
            try:
                vocabulary = Vocabulary.all_objects.get(slug=vocabulary_slug)
            except Vocabulary.DoesNotExist:
                raise CommandError(  # noqa: B904
                    f"Vocabulary with slug '{vocabulary_slug}' not found."
                )

        # --- Dry-run shortcut ---

        if dry_run:
            self._report_dry_run(data, vocabulary)
            return

        # --- Delegate to service ---

        from icv_taxonomy.services import import_vocabulary

        try:
            result = import_vocabulary(data, vocabulary=vocabulary)
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"Import failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete — "
                f"created: {result['created']}, "
                f"updated: {result['updated']}, "
                f"skipped: {result['skipped']}."
            )
        )

    def _report_dry_run(self, data: dict, vocabulary) -> None:  # type: ignore[no-untyped-def]
        """Report what an import would do without executing it."""
        vocab_name = vocabulary.name if vocabulary is not None else data.get("name", "<new vocabulary>")
        terms = data.get("terms", [])
        self.stdout.write(
            self.style.WARNING(f"[dry-run] Would import {len(terms)} term(s) into vocabulary '{vocab_name}'.")
        )
        self.stdout.write(self.style.WARNING("[dry-run] No changes written."))
