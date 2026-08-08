# Generated migration — Phase 2.3 Vector Search
# Adds pgvector embedding column to Video model.

import pgvector.django

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("videos", "0002_enable_pgvector_extension"),
    ]

    operations = [
        migrations.AddField(
            model_name="video",
            name="embedding",
            field=pgvector.django.VectorField(blank=True, dimensions=384, null=True),
        ),
    ]
