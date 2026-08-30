"""
embed.py
--------
Generate embeddings for all chunks using OpenAI text-embedding-3-small
and bulk-upsert into Supabase's document_chunks table.

Batching: 100 chunks per API call
Retry:    exponential backoff, max 3 retries on HTTP 429 / 500
Upsert:   conflict on chunk_id (idempotent re-runs)
"""

import json
import os
import time
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from tqdm import tqdm

load_dotenv()

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
BATCH_SIZE = 100

# ---------------------------------------------------------------------------
# OpenAI client
# ---------------------------------------------------------------------------

_client = None


def _get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY not set in environment or .env file")
        _client = OpenAI(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Retry-wrapped embedding call
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Call OpenAI embeddings API for a batch of texts.
    Returns list of embedding vectors in same order as input.
    """
    client = _get_openai_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    # Response embeddings are ordered by index
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def _get_db_conn():
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise EnvironmentError("SUPABASE_DB_URL not set in environment or .env file")
    return psycopg2.connect(db_url)


# ---------------------------------------------------------------------------
# Bulk upsert
# ---------------------------------------------------------------------------

UPSERT_SQL = """
INSERT INTO document_chunks
    (chunk_id, strategy, source_doc, source_page, char_start, char_end,
     token_count, chunk_text, embedding)
VALUES %s
ON CONFLICT (chunk_id) DO UPDATE SET
    strategy    = EXCLUDED.strategy,
    source_doc  = EXCLUDED.source_doc,
    source_page = EXCLUDED.source_page,
    char_start  = EXCLUDED.char_start,
    char_end    = EXCLUDED.char_end,
    token_count = EXCLUDED.token_count,
    chunk_text  = EXCLUDED.chunk_text,
    embedding   = EXCLUDED.embedding;
"""


def _upsert_batch(conn, rows: list[tuple]) -> None:
    """
    Bulk upsert a batch of rows into document_chunks.
    Each row: (chunk_id, strategy, source_doc, source_page, char_start,
               char_end, token_count, chunk_text, embedding_str)
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            UPSERT_SQL,
            rows,
            template=None,
            page_size=BATCH_SIZE,
        )
    conn.commit()


def _vector_to_pg(embedding: list[float]) -> str:
    """Convert a Python list of floats to pgvector literal string '[f1,f2,...]'."""
    return "[" + ",".join(str(v) for v in embedding) + "]"


# ---------------------------------------------------------------------------
# Main ingestion function
# ---------------------------------------------------------------------------

def embed_and_ingest(
    chunks: list[dict],
    output_dir: str = "data",
) -> None:
    """
    For each chunk in `chunks`:
      1. Batch embed via OpenAI API (100 chunks/call)
      2. Bulk upsert into document_chunks table

    Args:
        chunks:     List of chunk dicts from chunk.py
        output_dir: Directory to write embed_log.json (progress log)
    """
    if not chunks:
        print("No chunks to embed.")
        return

    output_dir = Path(output_dir)
    conn = _get_db_conn()

    total = len(chunks)
    print(f"\nEmbedding {total} chunks in batches of {BATCH_SIZE}...")
    print(f"  Model: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")

    embedded_count = 0
    failed_batches = []
    log_entries = []

    batches = [chunks[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

    for batch_idx, batch in enumerate(tqdm(batches, desc="Embedding batches")):
        texts = [c["chunk_text"] for c in batch]

        try:
            embeddings = _embed_batch(texts)
        except Exception as e:
            print(f"\n  ERROR on batch {batch_idx}: {e}")
            failed_batches.append(batch_idx)
            continue

        # Validate dimension
        for emb in embeddings:
            if len(emb) != EMBEDDING_DIM:
                raise ValueError(
                    f"Unexpected embedding dimension: {len(emb)} (expected {EMBEDDING_DIM})"
                )

        # Build DB rows
        rows = []
        for chunk, embedding in zip(batch, embeddings):
            rows.append((
                chunk["chunk_id"],
                chunk["strategy"],
                chunk["source_doc"],
                chunk["source_page"],
                chunk["char_start"],
                chunk["char_end"],
                chunk["token_count"],
                chunk["chunk_text"],
                _vector_to_pg(embedding),
            ))

        try:
            _upsert_batch(conn, rows)
            embedded_count += len(batch)
        except Exception as e:
            print(f"\n  DB ERROR on batch {batch_idx}: {e}")
            conn.rollback()
            failed_batches.append(batch_idx)
            continue

        log_entries.append({
            "batch": batch_idx,
            "count": len(batch),
            "strategy_sample": batch[0]["strategy"],
        })

    conn.close()

    # Write log
    log_path = output_dir / "embed_log.json"
    log_path.write_text(json.dumps({
        "total_chunks": total,
        "embedded": embedded_count,
        "failed_batches": failed_batches,
        "batches": log_entries,
    }, indent=2), encoding="utf-8")

    print(f"\n  Embedded and ingested: {embedded_count}/{total} chunks")
    if failed_batches:
        print(f"  WARNING: {len(failed_batches)} batches failed — see {log_path}")
    print(f"  Log written: {log_path}")


def verify_ingestion(expected_strategies: list[str] = None) -> None:
    """
    Print row counts per strategy from the database.
    Useful post-ingestion verification.
    """
    if expected_strategies is None:
        expected_strategies = ["fixed", "structural", "semantic"]

    conn = _get_db_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT strategy, COUNT(*) AS n, ROUND(AVG(token_count)) AS avg_tokens "
            "FROM document_chunks GROUP BY strategy ORDER BY strategy;"
        )
        rows = cur.fetchall()
    conn.close()

    print("\nIngestion verification:")
    print(f"  {'Strategy':<15} {'Count':>8} {'Avg Tokens':>12}")
    print(f"  {'-'*15} {'-'*8} {'-'*12}")
    found = set()
    for strategy, count, avg_tokens in rows:
        print(f"  {strategy:<15} {count:>8} {avg_tokens:>12}")
        found.add(strategy)

    missing = set(expected_strategies) - found
    if missing:
        print(f"\n  WARNING: Missing strategies in DB: {missing}")
    else:
        print(f"\n  All {len(expected_strategies)} strategies present in database.")


if __name__ == "__main__":
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"

    chunks_path = Path(data_dir) / "chunks.json"
    if not chunks_path.exists():
        print(f"chunks.json not found at {chunks_path}. Run chunk.py first.")
        sys.exit(1)

    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    embed_and_ingest(chunks, data_dir)
    verify_ingestion()
