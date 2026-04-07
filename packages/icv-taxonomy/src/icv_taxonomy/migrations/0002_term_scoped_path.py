# Generated manually — scopes path uniqueness per vocabulary.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("icv_taxonomy", "0001_initial"),
    ]

    operations = [
        # Step 1: Drop the global unique constraint on path.
        migrations.AlterField(
            model_name="term",
            name="path",
            field=models.CharField(
                db_index=True,
                editable=False,
                help_text=(
                    "Materialised path string (e.g. '0001/0002/0003'). Managed by icv-tree — do not edit directly."
                ),
                max_length=255,
                verbose_name="path",
            ),
        ),
        # Step 2: Add composite unique constraint (vocabulary, path).
        migrations.AlterUniqueTogether(
            name="term",
            unique_together={("vocabulary", "slug"), ("vocabulary", "path")},
        ),
    ]
