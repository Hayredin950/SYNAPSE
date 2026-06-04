# Generated migration — Phase 2.3 Vector Search
# Creates IVFFlat index on Video.embedding for fast cosine similarity search.
# SQLite-safe: skips on non-PostgreSQL backends.

from django.db import migrations


def create_ivfflat_index(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            CREATE INDEX IF NOT EXISTS
                videos_embedding_ivfflat_idx
            ON videos
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)


def drop_ivfflat_index(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("DROP INDEX IF EXISTS videos_embedding_ivfflat_idx;")


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("videos", "0003_video_embedding"),
    ]

    operations = [
        migrations.RunPython(create_ivfflat_index, drop_ivfflat_index),
    ]
