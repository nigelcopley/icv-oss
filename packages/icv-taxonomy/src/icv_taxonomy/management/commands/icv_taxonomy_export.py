"""
Management command: icv_taxonomy_export

Usage::

    python manage.py icv_taxonomy_export <vocabulary_slug>
    python manage.py icv_taxonomy_export <vocabulary_slug> --output <file_path>
    python manage.py icv_taxonomy_export <vocabulary_slug> --include-inactive

Exports a vocabulary (and all its terms) to JSON using the ``export_vocabulary``
service. Writes to stdout when ``--output`` is not specified.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Export a vocabulary to JSON."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "vocabulary_slug",
            type=str,
            help="Slug of the vocabulary to export.",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            metavar="FILE_PATH",
            help="Write output to this file path. Defaults to stdout.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            default=False,
            help="Include inactive terms in the export.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        vocabulary_slug: str = options["vocabulary_slug"]
        output_path: str | None = options["output"]
        include_inactive: bool = options["include_inactive"]

        # --- Resolve vocabulary ---

        from icv_taxonomy.conf import get_vocabulary_model

        Vocabulary = get_vocabulary_model()
        try:
            vocabulary = Vocabulary.all_objects.get(slug=vocabulary_slug)
        except Vocabulary.DoesNotExist:
            raise CommandError(  # noqa: B904
                f"Vocabulary with slug '{vocabulary_slug}' not found."
            )

        # --- Delegate to service ---

        from icv_taxonomy.services import export_vocabulary

        try:
            data = export_vocabulary(vocabulary, include_inactive=include_inactive)
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"Export failed: {exc}") from exc

        json_output = json.dumps(data, indent=2, ensure_ascii=False)

        # --- Write output ---

        if output_path is None:
            self.stdout.write(json_output)
        else:
            path = Path(output_path)
            try:
                path.write_text(json_output, encoding="utf-8")
            except OSError as exc:
                raise CommandError(f"Cannot write to {output_path}: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(f"Vocabulary '{vocabulary_slug}' exported to {path}."))
