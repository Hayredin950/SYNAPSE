# Generated migration — Phase 2.3 Vector Search
# Adds pgvector embedding column to Repository model.

import pgvector.django

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("repositories", "0002_enable_pgvector_extension"),
    ]

    operations = [
        migrations.AddField(
            model_name="repository",
            name="embedding",
            field=pgvector.django.VectorField(blank=True, dimensions=384, null=True),
        ),
    ]
