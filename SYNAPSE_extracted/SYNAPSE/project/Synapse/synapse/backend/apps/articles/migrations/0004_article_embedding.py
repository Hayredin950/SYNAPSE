# Generated migration — Phase 2.3 Vector Search
# Adds pgvector embedding column to Article model.

import pgvector.django

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0003_enable_pgvector_extension"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="embedding",
            field=pgvector.django.VectorField(blank=True, dimensions=384, null=True),
        ),
    ]
