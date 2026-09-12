-- ============================================================
-- Reset and recreate for all-MiniLM-L6-v2 (384 dim)
-- Run this in the Supabase SQL editor
-- ============================================================

-- 1. Drop existing
DROP INDEX IF EXISTS document_chunks_embedding_hnsw_idx;
DROP INDEX IF EXISTS document_chunks_strategy_idx;
DROP INDEX IF EXISTS document_chunks_source_page_idx;
DROP TABLE IF EXISTS document_chunks;
DROP FUNCTION IF EXISTS match_chunks;

-- 2. Recreate table with VECTOR(384)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
    id              BIGSERIAL       PRIMARY KEY,
    chunk_id        TEXT            NOT NULL UNIQUE,
    strategy        TEXT            NOT NULL
                    CHECK (strategy IN ('fixed', 'structural', 'semantic')),
    source_doc      TEXT            NOT NULL,
    source_page     SMALLINT        NOT NULL,
    char_start      INTEGER         NOT NULL,
    char_end        INTEGER         NOT NULL,
    token_count     SMALLINT        NOT NULL,
    chunk_text      TEXT            NOT NULL,
    embedding       VECTOR(384)     NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT char_order CHECK (char_end > char_start),
    CONSTRAINT token_positive CHECK (token_count > 0)
);

-- 3. HNSW index for 384-dim cosine search
CREATE INDEX document_chunks_embedding_hnsw_idx
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX document_chunks_strategy_idx ON document_chunks (strategy);
CREATE INDEX document_chunks_source_page_idx ON document_chunks (source_page);

-- 4. match_chunks RPC function for 384-dim
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding VECTOR(384),
    match_strategy  TEXT,
    match_count     INT DEFAULT 5
)
RETURNS TABLE (
    chunk_id    TEXT,
    strategy    TEXT,
    source_page SMALLINT,
    char_start  INTEGER,
    char_end    INTEGER,
    chunk_text  TEXT,
    similarity  FLOAT
)
LANGUAGE SQL STABLE
AS $$
    SELECT
        chunk_id,
        strategy,
        source_page,
        char_start,
        char_end,
        chunk_text,
        1 - (embedding <=> query_embedding) AS similarity
    FROM document_chunks
    WHERE strategy = match_strategy
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;
