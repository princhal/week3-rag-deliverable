-- ============================================================
-- match_chunks: vector similarity search RPC function
-- Run this in the Supabase SQL editor after 001_schema.sql
-- ============================================================

CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding VECTOR(768),
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
