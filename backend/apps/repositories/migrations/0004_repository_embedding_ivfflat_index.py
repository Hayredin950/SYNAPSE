# Generated migration — Phase 2.3 Vector Search
# Creates IVFFlat index on Repository.embedding for fast cosine similarity search.
# SQLite-safe: skips on non-PostgreSQL backends.

from django.db import migrations


def create_ivfflat_index(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            CREATE INDEX IF NOT EXISTS
                repositories_embedding_ivfflat_idx
            ON repositories
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)


def drop_ivfflat_index(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("DROP INDEX IF EXISTS repositories_embedding_ivfflat_idx;")


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("repositories", "0003_repository_embedding"),
    ]

    operations = [
        migrations.RunPython(create_ivfflat_index, drop_ivfflat_index),
    ]
