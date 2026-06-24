"""Tests for icv_taxonomy.tasks (orphan-cleanup Celery task).

The task is the automatic, schedulable counterpart to the manual
cleanup_orphaned_associations() service. Celery is optional — when absent the
task is a plain function, so these tests call it directly.
"""

from __future__ import annotations


class TestCleanupOrphanedAssociationsTask:
    """cleanup_orphaned_associations_task removes orphaned TermAssociation rows."""

    def test_task_removes_orphans_all_content_types(self, db):
        from django.apps import apps
        from taxonomy_testapp.models import Article

        from icv_taxonomy.services import create_term, create_vocabulary, tag_object
        from icv_taxonomy.tasks import cleanup_orphaned_associations_task

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Tag")
        article = Article.objects.create(title="To Delete")
        tag_object(term, article)
        article.delete()  # leaves the association orphaned (no FK cascade)

        stats = cleanup_orphaned_associations_task()

        assert stats["orphaned"] > 0
        assert stats["removed"] == stats["orphaned"]
        TermAssociation = apps.get_model("icv_taxonomy", "TermAssociation")
        assert not TermAssociation.objects.filter(term=term).exists()

    def test_task_restricts_to_model_label(self, db):
        from django.apps import apps
        from taxonomy_testapp.models import Article

        from icv_taxonomy.services import create_term, create_vocabulary, tag_object
        from icv_taxonomy.tasks import cleanup_orphaned_associations_task

        vocab = create_vocabulary(name="Tags", vocabulary_type="flat")
        term = create_term(vocabulary=vocab, name="Tag")
        article = Article.objects.create(title="To Delete")
        tag_object(term, article)
        article.delete()

        stats = cleanup_orphaned_associations_task(model_label="taxonomy_testapp.Article")

        assert stats["removed"] == stats["orphaned"]
        TermAssociation = apps.get_model("icv_taxonomy", "TermAssociation")
        assert not TermAssociation.objects.filter(term=term).exists()

    def test_task_noop_when_no_orphans(self, db):
        from icv_taxonomy.tasks import cleanup_orphaned_associations_task

        stats = cleanup_orphaned_associations_task()
        assert stats["orphaned"] == 0
        assert stats["removed"] == 0

    def test_task_is_importable_and_callable_without_celery(self):
        from icv_taxonomy.tasks import cleanup_orphaned_associations_task

        assert callable(cleanup_orphaned_associations_task)
