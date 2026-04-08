"""Tests for admin classes, management commands, and template tags.

Covers:
  - VocabularyAdmin and TermAdmin registration and configuration
  - VocabularyAdmin.get_queryset annotation and term_count display method
  - TermAdmin TreeAdmin mixin inheritance
  - icv_taxonomy_check management command
  - icv_taxonomy_export management command (stdout and file output)
  - icv_taxonomy_import management command (round-trip with export)
  - get_terms template tag (basic and with vocabulary filter)
  - get_vocabulary_terms template tag (all terms and roots_only)
  - has_term template tag
  - Template tag syntax error handling
"""

from __future__ import annotations

import json
import tempfile
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.management import call_command
from django.core.management.base import CommandError
from django.template import Context, Template, TemplateSyntaxError
from django.test import RequestFactory  # noqa: F401

# ===========================================================================
# Admin — VocabularyAdmin
# ===========================================================================


@pytest.mark.django_db
class TestVocabularyAdminRegistration:
    """VocabularyAdmin is registered on the default admin site."""

    def test_vocabulary_model_is_registered(self):
        """Vocabulary model appears in the default admin site registry."""
        from django.contrib import admin

        from icv_taxonomy.models import Vocabulary

        assert Vocabulary in admin.site._registry

    def test_vocabulary_admin_class_used(self):
        """The registered admin class is VocabularyAdmin."""
        from django.contrib import admin

        from icv_taxonomy.admin import VocabularyAdmin
        from icv_taxonomy.models import Vocabulary

        assert isinstance(admin.site._registry[Vocabulary], VocabularyAdmin)

    def test_vocabulary_admin_list_display(self):
        """VocabularyAdmin.list_display contains the expected columns."""
        from icv_taxonomy.admin import VocabularyAdmin

        expected = ("name", "slug", "vocabulary_type", "is_open", "term_count", "is_active")
        assert VocabularyAdmin.list_display == expected


@pytest.mark.django_db
class TestVocabularyAdminQueryset:
    """VocabularyAdmin.get_queryset annotates _term_count correctly."""

    def _make_request(self):
        factory = RequestFactory()
        request = factory.get("/admin/icv_taxonomy/vocabulary/")
        # Attach a minimal user stub so admin does not blow up on permission checks.
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
        return request

    def test_get_queryset_annotates_term_count(self, db):
        """Queryset returned by get_queryset has _term_count annotation."""
        from icv_taxonomy.admin import VocabularyAdmin
        from icv_taxonomy.models import Vocabulary

        Vocabulary.objects.create(name="Tags", slug="tags")

        site = AdminSite()
        admin_instance = VocabularyAdmin(Vocabulary, site)
        qs = admin_instance.get_queryset(self._make_request())

        vocab = qs.get(slug="tags")
        assert hasattr(vocab, "_term_count")

    def test_term_count_reflects_active_terms(self, db):
        """_term_count equals the number of active terms in the vocabulary."""
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Colours", slug="colours")
        Term(vocabulary=vocab, name="Red", slug="red", is_active=True).save()
        Term(vocabulary=vocab, name="Blue", slug="blue", is_active=True).save()
        # Inactive term — should NOT be counted.
        Term(vocabulary=vocab, name="Ghost", slug="ghost", is_active=False).save()

        from icv_taxonomy.admin import VocabularyAdmin

        site = AdminSite()
        admin_instance = VocabularyAdmin(Vocabulary, site)
        qs = admin_instance.get_queryset(self._make_request())

        vocab_annotated = qs.get(slug="colours")
        assert vocab_annotated._term_count == 2

    def test_term_count_display_method(self, db):
        """VocabularyAdmin.term_count() returns the _term_count annotation value."""
        from icv_taxonomy.admin import VocabularyAdmin
        from icv_taxonomy.models import Vocabulary

        Vocabulary.objects.create(name="Sizes", slug="sizes")

        site = AdminSite()
        admin_instance = VocabularyAdmin(Vocabulary, site)
        qs = admin_instance.get_queryset(self._make_request())
        vocab_annotated = qs.get(slug="sizes")

        result = admin_instance.term_count(vocab_annotated)
        assert result == 0

    def test_term_count_falls_back_to_zero_without_annotation(self, db):
        """term_count() returns 0 when _term_count annotation is absent."""
        from icv_taxonomy.admin import VocabularyAdmin
        from icv_taxonomy.models import Vocabulary

        vocab = Vocabulary(name="Bare", slug="bare")
        # Do not annotate — simulate a plain instance.
        admin_instance = VocabularyAdmin(Vocabulary, AdminSite())
        assert admin_instance.term_count(vocab) == 0


# ===========================================================================
# Admin — TermAdmin
# ===========================================================================


@pytest.mark.django_db
class TestTermAdminRegistration:
    """TermAdmin is registered on the default admin site."""

    def test_term_model_is_registered(self):
        """Term model appears in the default admin site registry."""
        from django.contrib import admin

        from icv_taxonomy.models import Term

        assert Term in admin.site._registry

    def test_term_admin_class_used(self):
        """The registered admin class is TermAdmin."""
        from django.contrib import admin

        from icv_taxonomy.admin import TermAdmin
        from icv_taxonomy.models import Term

        assert isinstance(admin.site._registry[Term], TermAdmin)

    def test_term_admin_list_display(self):
        """TermAdmin.list_display contains the expected columns."""
        from icv_taxonomy.admin import TermAdmin

        expected = ("indented_title", "slug", "vocabulary", "is_active")
        assert TermAdmin.list_display == expected

    def test_term_admin_has_tree_admin_mixin(self):
        """TermAdmin inherits from TreeAdmin when icv-tree is installed."""
        try:
            from icv_tree.admin import TreeAdmin
        except ImportError:
            pytest.skip("icv-tree not installed — TreeAdmin mixin unavailable")

        from icv_taxonomy.admin import TermAdmin

        assert issubclass(TermAdmin, TreeAdmin), "TermAdmin should inherit TreeAdmin when icv-tree is available"


# ===========================================================================
# Management command — icv_taxonomy_check
# ===========================================================================


@pytest.mark.django_db
class TestIcvTaxonomyCheckCommand:
    """icv_taxonomy_check runs successfully and reports clean data."""

    def test_check_passes_on_empty_db(self, db):
        """Command exits cleanly with no issues when the database is empty."""
        stdout = StringIO()
        # If issues are found the command raises SystemExit(1); clean = no exception.
        call_command("icv_taxonomy_check", stdout=stdout)
        output = stdout.getvalue()
        assert "passed" in output.lower()

    def test_check_passes_with_clean_flat_vocabulary(self, flat_vocabulary):
        """Command passes when a clean flat vocabulary with terms is present."""
        stdout = StringIO()
        call_command("icv_taxonomy_check", stdout=stdout)
        output = stdout.getvalue()
        assert "passed" in output.lower()

    def test_check_passes_with_clean_hierarchical_vocabulary(self, hierarchical_vocabulary):
        """Command passes when a clean hierarchical vocabulary is present."""
        stdout = StringIO()
        call_command("icv_taxonomy_check", stdout=stdout)
        output = stdout.getvalue()
        assert "passed" in output.lower()

    def test_check_detects_flat_vocabulary_type_violation(self, db):
        """Command exits 1 when a flat vocabulary term has a parent set."""
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Flat Bad", slug="flat-bad", vocabulary_type="flat")
        parent = Term(vocabulary=vocab, name="Parent", slug="parent-term")
        parent.save()
        # Bypass validation to inject the violation directly.
        Term.all_objects.filter(pk=parent.pk).update(parent=None)
        child = Term(vocabulary=vocab, name="Child", slug="child-term")
        child.save()
        Term.all_objects.filter(pk=child.pk).update(parent=parent)

        stdout = StringIO()
        stderr = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command("icv_taxonomy_check", stdout=stdout, stderr=stderr)
        assert exc_info.value.code == 1

    def test_check_fix_repairs_flat_vocabulary_type_violation(self, db):
        """--fix removes parent references from flat vocabulary terms."""
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Fix Flat", slug="fix-flat", vocabulary_type="flat")
        parent = Term(vocabulary=vocab, name="Parent Fix", slug="parent-fix")
        parent.save()
        child = Term(vocabulary=vocab, name="Child Fix", slug="child-fix")
        child.save()
        Term.all_objects.filter(pk=child.pk).update(parent=parent)

        stdout = StringIO()
        call_command("icv_taxonomy_check", fix=True, stdout=stdout)
        output = stdout.getvalue()
        assert "Fixed" in output or "fixed" in output.lower()

        child.refresh_from_db()
        assert child.parent_id is None


# ===========================================================================
# Management command — icv_taxonomy_export
# ===========================================================================


@pytest.mark.django_db
class TestIcvTaxonomyExportCommand:
    """icv_taxonomy_export serialises a vocabulary to JSON."""

    def test_export_writes_valid_json_to_stdout(self, flat_vocabulary):
        """Export command writes valid JSON to stdout for a known vocabulary."""
        stdout = StringIO()
        call_command("icv_taxonomy_export", flat_vocabulary.slug, stdout=stdout)
        data = json.loads(stdout.getvalue())
        assert data["slug"] == flat_vocabulary.slug

    def test_export_json_contains_terms(self, flat_vocabulary):
        """Exported JSON contains the vocabulary's active terms."""
        stdout = StringIO()
        call_command("icv_taxonomy_export", flat_vocabulary.slug, stdout=stdout)
        data = json.loads(stdout.getvalue())
        assert len(data["terms"]) == 5

    def test_export_raises_command_error_for_unknown_slug(self, db):
        """CommandError is raised when the vocabulary slug does not exist."""
        with pytest.raises(CommandError, match="not found"):
            call_command("icv_taxonomy_export", "no-such-vocabulary")

    def test_export_to_file(self, flat_vocabulary):
        """Export writes valid JSON file when --output is provided."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        stdout = StringIO()
        call_command("icv_taxonomy_export", flat_vocabulary.slug, output=tmp_path, stdout=stdout)

        content = Path(tmp_path).read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["slug"] == flat_vocabulary.slug

    def test_export_include_inactive_includes_inactive_terms(self, db):
        """--include-inactive adds inactive terms to the exported JSON."""
        from icv_taxonomy.models import Term, Vocabulary

        vocab = Vocabulary.objects.create(name="Mixed", slug="mixed")
        Term(vocabulary=vocab, name="Active Term", slug="active-term", is_active=True).save()
        Term(vocabulary=vocab, name="Inactive Term", slug="inactive-term", is_active=False).save()

        stdout_active = StringIO()
        call_command("icv_taxonomy_export", "mixed", stdout=stdout_active)
        active_data = json.loads(stdout_active.getvalue())
        assert len(active_data["terms"]) == 1

        stdout_all = StringIO()
        call_command("icv_taxonomy_export", "mixed", include_inactive=True, stdout=stdout_all)
        all_data = json.loads(stdout_all.getvalue())
        assert len(all_data["terms"]) == 2


# ===========================================================================
# Management command — icv_taxonomy_import
# ===========================================================================


@pytest.mark.django_db
class TestIcvTaxonomyImportCommand:
    """icv_taxonomy_import reads JSON and creates vocabulary and terms."""

    def _write_json(self, data: dict) -> str:
        """Write *data* to a temp file and return the path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(data, tmp)
            return tmp.name

    def test_import_creates_vocabulary_and_terms(self, db):
        """Import command creates a new vocabulary with terms from JSON."""
        from icv_taxonomy.models import Term, Vocabulary

        data = {
            "name": "Imported Vocab",
            "slug": "imported-vocab",
            "description": "",
            "vocabulary_type": "flat",
            "is_open": True,
            "allow_multiple": True,
            "max_depth": None,
            "metadata": {},
            "terms": [
                {
                    "name": "Alpha",
                    "slug": "alpha",
                    "description": "",
                    "parent_slug": None,
                    "is_active": True,
                    "metadata": {},
                },
                {
                    "name": "Beta",
                    "slug": "beta",
                    "description": "",
                    "parent_slug": None,
                    "is_active": True,
                    "metadata": {},
                },
            ],
            "relationships": [],
        }
        path = self._write_json(data)
        stdout = StringIO()
        call_command("icv_taxonomy_import", path, stdout=stdout)

        assert Vocabulary.objects.filter(slug="imported-vocab").exists()
        assert Term.objects.filter(vocabulary__slug="imported-vocab").count() == 2

    def test_import_raises_command_error_for_missing_file(self, db):
        """CommandError is raised when the file path does not exist."""
        with pytest.raises(CommandError, match="File not found"):
            call_command("icv_taxonomy_import", "/tmp/does-not-exist-9999.json")

    def test_import_raises_command_error_for_invalid_json(self, db):
        """CommandError is raised when the file contains invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            tmp.write("this is not json {{{")
            bad_path = tmp.name

        with pytest.raises(CommandError, match="Invalid JSON"):
            call_command("icv_taxonomy_import", bad_path)

    def test_import_dry_run_does_not_write(self, db):
        """--dry-run reports the intended changes but writes nothing."""
        from icv_taxonomy.models import Vocabulary

        data = {
            "name": "Dry Vocab",
            "slug": "dry-vocab",
            "description": "",
            "vocabulary_type": "flat",
            "is_open": True,
            "allow_multiple": True,
            "max_depth": None,
            "metadata": {},
            "terms": [
                {
                    "name": "One",
                    "slug": "one",
                    "description": "",
                    "parent_slug": None,
                    "is_active": True,
                    "metadata": {},
                },
            ],
            "relationships": [],
        }
        path = self._write_json(data)
        stdout = StringIO()
        call_command("icv_taxonomy_import", path, dry_run=True, stdout=stdout)

        assert not Vocabulary.objects.filter(slug="dry-vocab").exists()
        assert "dry-run" in stdout.getvalue().lower()

    def test_round_trip_export_then_import(self, flat_vocabulary):
        """Vocabulary exported then imported produces matching term count."""
        from icv_taxonomy.models import Term

        # Export to a temp file.
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            export_path = tmp.name

        call_command("icv_taxonomy_export", flat_vocabulary.slug, output=export_path)

        # Remove all terms from the vocabulary to simulate a fresh import target.
        Term.all_objects.filter(vocabulary=flat_vocabulary).delete()
        assert Term.objects.filter(vocabulary=flat_vocabulary).count() == 0

        # Import back into the same vocabulary.
        stdout = StringIO()
        call_command("icv_taxonomy_import", export_path, vocabulary=flat_vocabulary.slug, stdout=stdout)

        assert Term.objects.filter(vocabulary=flat_vocabulary).count() == 5


# ===========================================================================
# Template tags
# ===========================================================================


@pytest.mark.django_db
class TestGetTermsTag:
    """get_terms template tag populates context variable with term queryset."""

    def test_get_terms_for_tagged_object(self, tagged_article):
        """get_terms populates context with terms for a tagged object."""
        tmpl = Template("{% load icv_taxonomy %}{% get_terms for article as terms %}{{ terms|length }}")
        ctx = Context({"article": tagged_article})
        result = tmpl.render(ctx)
        assert result == "1"

    def test_get_terms_for_untagged_object_returns_empty(self, article):
        """get_terms returns an empty queryset for an untagged object."""
        tmpl = Template("{% load icv_taxonomy %}{% get_terms for article as terms %}{{ terms|length }}")
        ctx = Context({"article": article})
        result = tmpl.render(ctx)
        assert result == "0"

    def test_get_terms_with_vocabulary_filter(self, tagged_article, flat_vocabulary):
        """get_terms with vocabulary slug filters to terms in that vocabulary."""
        tmpl = Template(
            '{% load icv_taxonomy %}{% get_terms for article vocabulary "flat-vocab" as terms %}{{ terms|length }}'
        )
        ctx = Context({"article": tagged_article})
        result = tmpl.render(ctx)
        assert result == "1"

    def test_get_terms_with_wrong_vocabulary_returns_empty(self, tagged_article):
        """get_terms with a non-matching vocabulary slug returns empty queryset."""
        tmpl = Template(
            '{% load icv_taxonomy %}{% get_terms for article vocabulary "no-such-vocab" as terms %}{{ terms|length }}'
        )
        ctx = Context({"article": tagged_article})
        result = tmpl.render(ctx)
        assert result == "0"

    def test_get_terms_missing_variable_does_not_raise(self):
        """get_terms renders empty when the object variable is not in context."""
        tmpl = Template("{% load icv_taxonomy %}{% get_terms for missing_var as terms %}{{ terms|length }}")
        ctx = Context({})
        # Should render silently, not raise.
        result = tmpl.render(ctx)
        assert result == "0"

    def test_get_terms_bad_syntax_raises_template_syntax_error(self):
        """Malformed get_terms tag raises TemplateSyntaxError at parse time."""
        with pytest.raises(TemplateSyntaxError):
            Template("{% load icv_taxonomy %}{% get_terms for %}")


@pytest.mark.django_db
class TestGetVocabularyTermsTag:
    """get_vocabulary_terms simple_tag returns terms for a given vocabulary slug."""

    def test_returns_all_active_terms(self, flat_vocabulary):
        """Tag returns all active terms for the named vocabulary."""
        tmpl = Template('{% load icv_taxonomy %}{% get_vocabulary_terms "flat-vocab" as terms %}{{ terms|length }}')
        ctx = Context({})
        result = tmpl.render(ctx)
        assert result == "5"

    def test_returns_empty_for_unknown_slug(self, db):
        """Tag returns an empty queryset for a vocabulary slug that does not exist."""
        tmpl = Template('{% load icv_taxonomy %}{% get_vocabulary_terms "does-not-exist" as terms %}{{ terms|length }}')
        ctx = Context({})
        result = tmpl.render(ctx)
        assert result == "0"

    def test_roots_only_filters_to_root_terms(self, hierarchical_vocabulary):
        """roots_only=True returns only root-level (parentless) terms."""
        tmpl = Template(
            "{% load icv_taxonomy %}"
            '{% get_vocabulary_terms "hierarchical-vocab" roots_only=True as roots %}'
            "{{ roots|length }}"
        )
        ctx = Context({})
        result = tmpl.render(ctx)
        # hierarchical_vocabulary fixture has exactly 1 root term ("root").
        assert result == "1"

    def test_without_roots_only_returns_all_terms(self, hierarchical_vocabulary):
        """Without roots_only, all 10 terms in the hierarchical vocabulary are returned."""
        tmpl = Template(
            '{% load icv_taxonomy %}{% get_vocabulary_terms "hierarchical-vocab" as all_terms %}{{ all_terms|length }}'
        )
        ctx = Context({})
        result = tmpl.render(ctx)
        # 1 root + 3 children + 6 grandchildren = 10
        assert result == "10"


@pytest.mark.django_db
class TestHasTermTag:
    """has_term simple_tag returns True/False for term membership."""

    def test_has_term_returns_true_for_tagged_object(self, tagged_article, flat_vocabulary):
        """has_term is True when the object is tagged with the named term."""
        # The tagged_article fixture tags the first term of flat_vocabulary.
        first_term_slug = flat_vocabulary.terms.first().slug
        tmpl = Template(
            '{% load icv_taxonomy %}{% has_term article "flat-vocab" "' + first_term_slug + '" as result %}{{ result }}'
        )
        ctx = Context({"article": tagged_article})
        result = tmpl.render(ctx)
        assert result == "True"

    def test_has_term_returns_false_for_untagged_object(self, article, flat_vocabulary):
        """has_term is False when the object is not tagged with the term."""
        first_term_slug = flat_vocabulary.terms.first().slug
        tmpl = Template(
            '{% load icv_taxonomy %}{% has_term article "flat-vocab" "' + first_term_slug + '" as result %}{{ result }}'
        )
        ctx = Context({"article": article})
        result = tmpl.render(ctx)
        assert result == "False"

    def test_has_term_returns_false_for_nonexistent_term(self, tagged_article):
        """has_term is False when the vocabulary or term slug does not exist."""
        tmpl = Template(
            '{% load icv_taxonomy %}{% has_term article "flat-vocab" "no-such-term" as result %}{{ result }}'
        )
        ctx = Context({"article": tagged_article})
        result = tmpl.render(ctx)
        assert result == "False"

    def test_has_term_returns_false_for_nonexistent_vocabulary(self, tagged_article):
        """has_term is False when the vocabulary slug does not exist."""
        tmpl = Template('{% load icv_taxonomy %}{% has_term article "no-such-vocab" "term-1" as result %}{{ result }}')
        ctx = Context({"article": tagged_article})
        result = tmpl.render(ctx)
        assert result == "False"
