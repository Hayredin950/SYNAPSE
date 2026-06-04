# Generated migration — Phase 2.3 Vector Search
# Adds pgvector embedding column to ResearchPaper model.

import pgvector.django

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("papers", "0002_enable_pgvector_extension"),
    ]

    operations = [
        migrations.AddField(
            model_name="researchpaper",
            name="embedding",
            field=pgvector.django.VectorField(blank=True, dimensions=384, null=True),
        ),
    ]
