"""
Migration: Add tsvector search_vector column + GIN index to ResearchPaper.

TASK-301 — Hybrid Search (BM25 + Semantic + Reranking)

Weight mapping:
  A — title     (highest)
  B — abstract  (high)
  C — summary   (medium)
  D — authors   (low)
"""
from django.db import migrations

TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION papers_search_vector_update()
RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
      setweight(to_tsvector('english', coalesce(NEW.title, '')),                             'A') ||
      setweight(to_tsvector('english', coalesce(NEW.abstract, '')),                          'B') ||
      setweight(to_tsvector('english', coalesce(NEW.summary, '')),                           'C') ||
      setweight(to_tsvector('english', coalesce(array_to_string(NEW.authors, ' '), '')),     'D');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS papers_search_vector_trigger ON research_papers;
CREATE TRIGGER papers_search_vector_trigger
BEFORE INSERT OR UPDATE OF title, abstract, summary, authors
ON research_papers
FOR EACH ROW EXECUTE FUNCTION papers_search_vector_update();
"""

TRIGGER_REVERT_SQL = """
DROP TRIGGER IF EXISTS papers_search_vector_trigger ON research_papers;
DROP FUNCTION IF EXISTS papers_search_vector_update();
"""

BACKFILL_SQL = """
UPDATE research_papers SET search_vector =
    setweight(to_tsvector('english', coalesce(title, '')),                         'A') ||
    setweight(to_tsvector('english', coalesce(abstract, '')),                      'B') ||
    setweight(to_tsvector('english', coalesce(summary, '')),                       'C') ||
    setweight(to_tsvector('english', coalesce(array_to_string(authors, ' '), '')), 'D');
"""


class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0005_paper_embedding_1024'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE research_papers ADD COLUMN IF NOT EXISTS search_vector tsvector;",
            reverse_sql="ALTER TABLE research_papers DROP COLUMN IF EXISTS search_vector;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS papers_search_vector_gin ON research_papers USING gin(search_vector);",
            reverse_sql="DROP INDEX IF EXISTS papers_search_vector_gin;",
        ),
        migrations.RunSQL(sql=TRIGGER_SQL, reverse_sql=TRIGGER_REVERT_SQL),
        migrations.RunSQL(sql=BACKFILL_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
