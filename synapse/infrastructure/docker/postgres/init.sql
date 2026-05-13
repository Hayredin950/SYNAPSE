-- SYNAPSE PostgreSQL initialization script
-- Enables pgvector extension for semantic search

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Create additional indexes support
ALTER DATABASE synapse_db SET timezone TO 'UTC';
