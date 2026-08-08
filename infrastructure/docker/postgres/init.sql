-- SYNAPSE — PostgreSQL initialisation
--
-- Runs once, on first container start, before Django migrations.
-- pgvector must exist before any migration creates a `vector` column, and
-- CREATE EXTENSION requires superuser — which migrations run as the app user
-- do not have. So it happens here instead.

CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector: embedding columns + ANN search
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- trigram similarity for fuzzy text search
CREATE EXTENSION IF NOT EXISTS unaccent;    -- accent-insensitive search

-- Confirm in the container log that extensions are present.
DO $$
DECLARE
    ext_list text;
BEGIN
    SELECT string_agg(extname, ', ' ORDER BY extname)
      INTO ext_list
      FROM pg_extension
     WHERE extname IN ('vector', 'pg_trgm', 'unaccent');
    RAISE NOTICE '[SYNAPSE] extensions ready: %', ext_list;
END $$;
