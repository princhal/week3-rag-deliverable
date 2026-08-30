-- ============================================================
-- Reset script — drops and recreates the table and indexes
-- USE WITH CAUTION: deletes all ingested data
-- ============================================================

DROP INDEX IF EXISTS document_chunks_embedding_hnsw_idx;
DROP INDEX IF EXISTS document_chunks_strategy_idx;
DROP INDEX IF EXISTS document_chunks_source_page_idx;
DROP TABLE IF EXISTS document_chunks;

-- Re-run 001_schema.sql after this to recreate
