"""
Migration: Add tsvector search_vector column + GIN index to Article.

TASK-301 — Hybrid Search (BM25 + Semantic + Reranking)

The search_vector is kept up-to-date by a PostgreSQL trigger that fires on
INSERT/UPDATE of title, content, or summary, so application code never needs
to compute it manually.

Weight mapping:
  A — title         (highest)
  B — summary       (high)
  C — content       (medium)
  D — author/topic  (low)
"""
from django.db import migrations

# Raw SQL for the trigger + function (DB-level, not managed by Django ORM)
TRIGGER_SQL = """
-- Function: recompute search_vector on every article write
CREATE OR REPLACE FUNCTION articles_search_vector_update()
RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
      setweight(to_tsvector('english', coalesce(NEW.title, '')),   'A') ||
      setweight(to_tsvector('english', coalesce(NEW.summary, '')), 'B') ||
      setweight(to_tsvector('english', coalesce(NEW.content, '')), 'C') ||
      setweight(to_tsvector('english', coalesce(NEW.author, '') || ' ' || coalesce(NEW.topic, '')), 'D');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on INSERT / UPDATE of searchable columns
DROP TRIGGER IF EXISTS articles_search_vector_trigger ON articles;
CREATE TRIGGER articles_search_vector_trigger
BEFORE INSERT OR UPDATE OF title, summary, content, author, topic
ON articles
FOR EACH ROW EXECUTE FUNCTION articles_search_vector_update();
"""

TRIGGER_REVERT_SQL = """
DROP TRIGGER IF EXISTS articles_search_vector_trigger ON articles;
DROP FUNCTION IF EXISTS articles_search_vector_update();
"""

BACKFILL_SQL = """
UPDATE articles SET search_vector =
    setweight(to_tsvector('english', coalesce(title, '')),   'A') ||
    setweight(to_tsvector('english', coalesce(summary, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(content, '')), 'C') ||
    setweight(to_tsvector('english', coalesce(author, '') || ' ' || coalesce(topic, '')), 'D');
"""


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0005_article_embedding_1024'),
    ]

    operations = [
        # 1. Add the tsvector column (nullable until backfilled)
        migrations.RunSQL(
            sql="ALTER TABLE articles ADD COLUMN IF NOT EXISTS search_vector tsvector;",
            reverse_sql="ALTER TABLE articles DROP COLUMN IF EXISTS search_vector;",
        ),

        # 2. GIN index for fast full-text search
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS articles_search_vector_gin ON articles USING gin(search_vector);",
            reverse_sql="DROP INDEX IF EXISTS articles_search_vector_gin;",
        ),

        # 3. Create trigger + function
        migrations.RunSQL(sql=TRIGGER_SQL, reverse_sql=TRIGGER_REVERT_SQL),

        # 4. Backfill existing rows
        migrations.RunSQL(sql=BACKFILL_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
