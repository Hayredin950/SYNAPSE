"""
Migration: add/upgrade embedding column (vector 1024) to tweets table.

TASK-005-B2 — Upgrade embeddings to BAAI/bge-large-en-v1.5

Uses DO $$ guards to be safe on both fresh and existing DBs (table may not exist yet).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tweets", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    -- Ensure pgvector extension exists (no-op if already present)
                    CREATE EXTENSION IF NOT EXISTS vector;

                    -- Only operate if the tweets table exists
                    IF EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name='tweets_tweet'
                    ) THEN
                        -- Add embedding column if it doesn't exist
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='tweets_tweet' AND column_name='embedding'
                        ) THEN
                            EXECUTE 'ALTER TABLE tweets_tweet ADD COLUMN embedding vector(1024)';
                        ELSE
                            -- Already exists — upgrade dimensions if needed
                            EXECUTE 'ALTER TABLE tweets_tweet ALTER COLUMN embedding TYPE vector(1024) USING embedding::text::vector(1024)';
                        END IF;

                        -- Create ivfflat index
                        CREATE INDEX IF NOT EXISTS tweets_tweet_embedding_ivfflat_idx
                        ON tweets_tweet
                        USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 100);
                    END IF;
                END $$;
            """,
            reverse_sql="""
                DO $$
                BEGIN
                    DROP INDEX IF EXISTS tweets_tweet_embedding_ivfflat_idx;
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='tweets_tweet' AND column_name='embedding'
                    ) THEN
                        EXECUTE 'ALTER TABLE tweets_tweet DROP COLUMN embedding';
                    END IF;
                END $$;
            """,
        ),
    ]
