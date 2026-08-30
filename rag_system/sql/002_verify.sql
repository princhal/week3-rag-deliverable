-- ============================================================
-- Verification queries — run after 001_schema.sql
-- All checks should return the expected values shown in comments
-- ============================================================

-- 1. Confirm pgvector version (must be >= 0.5.0 for HNSW support)
SELECT extversion AS pgvector_version
FROM pg_extension
WHERE extname = 'vector';
-- Expected: 0.5.0 or higher

-- 2. Confirm table exists with correct columns
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'document_chunks'
ORDER BY ordinal_position;
-- Expected: 11 rows matching the schema definition

-- 3. Confirm HNSW index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'document_chunks'
  AND indexname = 'document_chunks_embedding_hnsw_idx';
-- Expected: 1 row with USING hnsw

-- 4. Confirm index parameters
SELECT
    i.relname AS index_name,
    ix.reloptions AS index_options
FROM pg_class i
JOIN pg_index idx ON i.oid = idx.indexrelid
JOIN pg_class ix ON ix.oid = idx.indrelid
JOIN pg_opclass op ON op.oid = ANY(idx.indclass)
WHERE i.relname = 'document_chunks_embedding_hnsw_idx';
-- Expected: reloptions shows m=16, ef_construction=64

-- 5. Row count by strategy (run after ingestion)
SELECT strategy, COUNT(*) AS chunk_count, ROUND(AVG(token_count)) AS avg_tokens
FROM document_chunks
GROUP BY strategy
ORDER BY strategy;
-- Expected after ingestion: 3 rows (fixed, structural, semantic)
