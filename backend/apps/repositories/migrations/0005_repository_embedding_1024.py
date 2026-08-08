"""
Migration: alter repositories_repository embedding column from vector(384) to vector(1024).

TASK-005-B2 — Upgrade embeddings to BAAI/bge-large-en-v1.5

Uses DO $$ guards so migration is safe on fresh test DBs and in transactions.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("repositories", "0004_repository_embedding_ivfflat_index"),
    ]

    operations = [
        # Safe: only acts if table+column exist
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    -- Drop old index if exists
                    DROP INDEX IF EXISTS repositories_repository_embedding_ivfflat_idx;
                    -- Alter column only if it exists
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='repositories_repository' AND column_name='embedding'
                    ) THEN
                        EXECUTE 'ALTER TABLE repositories_repository ALTER COLUMN embedding TYPE vector(1024) USING embedding::text::vector(1024)';
                    END IF;
                    -- Recreate index only if table exists
                    IF EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name='repositories_repository'
                    ) THEN
                        EXECUTE 'CREATE INDEX IF NOT EXISTS repositories_repository_embedding_ivfflat_idx ON repositories_repository USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)';
                    END IF;
                END $$;
            """,
            reverse_sql="""
                DO $$
                BEGIN
                    DROP INDEX IF EXISTS repositories_repository_embedding_ivfflat_idx;
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='repositories_repository' AND column_name='embedding'
                    ) THEN
                        EXECUTE 'ALTER TABLE repositories_repository ALTER COLUMN embedding TYPE vector(384) USING embedding::text::vector(384)';
                    END IF;
                END $$;
            """,
        ),
    ]
