"""
Migration: Add tsvector search_vector column + GIN index to Repository.

TASK-301 — Hybrid Search (BM25 + Semantic + Reranking)

Weight mapping:
  A — name        (highest)
  B — description (high)
  C — language    (medium)
  D — owner       (low)
"""
from django.db import migrations

TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION repos_search_vector_update()
RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
      setweight(to_tsvector('english', coalesce(NEW.name, '')),        'A') ||
      setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B') ||
      setweight(to_tsvector('english', coalesce(NEW.language, '')),    'C') ||
      setweight(to_tsvector('english', coalesce(NEW.owner, '')),       'D');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS repos_search_vector_trigger ON repositories;
CREATE TRIGGER repos_search_vector_trigger
BEFORE INSERT OR UPDATE OF name, description, language, owner
ON repositories
FOR EACH ROW EXECUTE FUNCTION repos_search_vector_update();
"""

TRIGGER_REVERT_SQL = """
DROP TRIGGER IF EXISTS repos_search_vector_trigger ON repositories;
DROP FUNCTION IF EXISTS repos_search_vector_update();
"""

BACKFILL_SQL = """
UPDATE repositories SET search_vector =
    setweight(to_tsvector('english', coalesce(name, '')),        'A') ||
    setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(language, '')),    'C') ||
    setweight(to_tsvector('english', coalesce(owner, '')),       'D');
"""


class Migration(migrations.Migration):

    dependencies = [
        ('repositories', '0005_repository_embedding_1024'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE repositories ADD COLUMN IF NOT EXISTS search_vector tsvector;",
            reverse_sql="ALTER TABLE repositories DROP COLUMN IF EXISTS search_vector;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS repos_search_vector_gin ON repositories USING gin(search_vector);",
            reverse_sql="DROP INDEX IF EXISTS repos_search_vector_gin;",
        ),
        migrations.RunSQL(sql=TRIGGER_SQL, reverse_sql=TRIGGER_REVERT_SQL),
        migrations.RunSQL(sql=BACKFILL_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
