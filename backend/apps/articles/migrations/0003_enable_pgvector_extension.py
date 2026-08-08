# Generated migration — Phase 2.3 Vector Search
# Enables the pgvector extension in PostgreSQL (required before vector columns).
# SQLite-safe: skips the CREATE EXTENSION statement on non-PostgreSQL backends.

from django.db import connection, migrations


def enable_pgvector(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS vector;")


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0002_article_nlp_processed"),
    ]

    operations = [
        migrations.RunPython(enable_pgvector, migrations.RunPython.noop),
    ]
