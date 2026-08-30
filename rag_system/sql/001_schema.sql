-- ============================================================
-- RAG System: Supabase pgvector Schema
-- Run this once in the Supabase SQL editor or via psql
-- ============================================================

-- 1. Enable pgvector extension (requires Supabase pgvector support)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Main chunks table
CREATE TABLE IF NOT EXISTS document_chunks (
    id              BIGSERIAL       PRIMARY KEY,
    chunk_id        TEXT            NOT NULL UNIQUE,   -- e.g. fixed_p04_003
    strategy        TEXT            NOT NULL            -- 'fixed' | 'structural' | 'semantic'
                    CHECK (strategy IN ('fixed', 'structural', 'semantic')),
    source_doc      TEXT            NOT NULL,           -- source PDF filename
    source_page     SMALLINT        NOT NULL,           -- 1-based page number
    char_start      INTEGER         NOT NULL,           -- offset in cleaned full-text (inclusive)
    char_end        INTEGER         NOT NULL,           -- offset in cleaned full-text (exclusive)
    token_count     SMALLINT        NOT NULL,           -- tiktoken cl100k_base count
    chunk_text      TEXT            NOT NULL,           -- raw chunk text
    embedding       VECTOR(1536)    NOT NULL,           -- text-embedding-3-small output
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT char_order CHECK (char_end > char_start),
    CONSTRAINT token_positive CHECK (token_count > 0)
);

-- 3. HNSW index on embedding column using cosine distance
--    m=16, ef_construction=64 — well-tuned for < 1k vectors
CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 4. Supporting indexes for filtered queries
CREATE INDEX IF NOT EXISTS document_chunks_strategy_idx
    ON document_chunks (strategy);

CREATE INDEX IF NOT EXISTS document_chunks_source_page_idx
    ON document_chunks (source_page);
