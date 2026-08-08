"""Widen Video.embedding to vector(1024).

The earlier `*_embedding_1024` migration was meant to do this but is a silent
no-op: its `IF EXISTS` guard tests Django's default table name
(e.g. "videos_video") while the model defines a custom db_table, so the
condition is never true and the ALTER never runs.

This migration uses AlterField instead, so Django emits the statement against
the real table name — and stays correct if the table is ever renamed.
"""

import pgvector.django.vector
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("videos", "0007_remove_video_user_uservideo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="video",
            name="embedding",
            field=pgvector.django.vector.VectorField(
                blank=True, dimensions=1024, null=True
            ),
        ),
    ]
