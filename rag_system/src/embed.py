"""
embed.py
--------
Generate embeddings for all chunks using local sentence-transformers
(all-MiniLM-L6-v2, 384 dimensions, CPU-only, no API key needed)
and bulk-upsert into Supabase's document_chunks table.

Model:    sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
Batching: 100 chunks per call
Upsert:   conflict on chunk_id (idempotent re-runs)
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client, Client
from tqdm import tqdm

load_dotenv()

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
BATCH_SIZE = 100

# Lazy-load model (downloads ~90MB on first run, cached after)
_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"  Loading model: {EMBEDDING_MODEL_NAME} (first run downloads ~90MB)...")
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


# ---------------------------------------------------------------------------
# Embedding functions (same signatures as before)
# ---------------------------------------------------------------------------

def _embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of texts for indexing (document chunks).
    Returns list of 384-dim vectors in same order as input.
    """
    model = _get_model()
    embeddings = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False)
    return embeddings.tolist()


def _embed_query(text: str) -> list[float]:
    """
    Embed a single query string for retrieval.
    """
    model = _get_model()
    embedding = model.encode([text], show_progress_bar=False)
    return embedding[0].tolist()


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(url, key)


def _upsert_batch(client: Client, rows: list[dict]) -> None:
    """Bulk upsert a batch of chunk dicts into document_chunks via Supabase."""
    client.table("document_chunks").upsert(rows, on_conflict="chunk_id").execute()


# ---------------------------------------------------------------------------
# Main ingestion function
# ---------------------------------------------------------------------------

def embed_and_ingest(
    chunks: list[dict],
    output_dir: str = "data",
) -> None:
    """
    For each chunk:
      1. Batch embed locally via sentence-transformers
      2. Bulk upsert into document_chunks table
    """
    if not chunks:
        print("No chunks to embed.")
        return

    output_dir = Path(output_dir)
    client = _get_supabase_client()

    total = len(chunks)
    print(f"\nEmbedding {total} chunks locally in batches of {BATCH_SIZE}...")
    print(f"  Model: {EMBEDDING_MODEL_NAME} (dim={EMBEDDING_DIM}, CPU-only)")

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

        # Build rows as dicts for Supabase client
        rows = []
        for chunk, embedding in zip(batch, embeddings):
            rows.append({
                "chunk_id":    chunk["chunk_id"],
                "strategy":    chunk["strategy"],
                "source_doc":  chunk["source_doc"],
                "source_page": chunk["source_page"],
                "char_start":  chunk["char_start"],
                "char_end":    chunk["char_end"],
                "token_count": chunk["token_count"],
                "chunk_text":  chunk["chunk_text"],
                "embedding":   embedding,
            })

        try:
            _upsert_batch(client, rows)
            embedded_count += len(batch)
        except Exception as e:
            print(f"\n  DB ERROR on batch {batch_idx}: {e}")
            failed_batches.append(batch_idx)
            continue

        log_entries.append({
            "batch": batch_idx,
            "count": len(batch),
            "strategy_sample": batch[0]["strategy"],
        })

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
    """Print row counts per strategy from the database."""
    if expected_strategies is None:
        expected_strategies = ["fixed", "structural", "semantic"]

    client = _get_supabase_client()
    response = client.table("document_chunks").select("strategy, token_count").execute()
    rows = response.data

    from collections import Counter
    counts = Counter(r["strategy"] for r in rows)
    token_sums: dict = {}
    token_counts_by_strategy: dict = {}
    for r in rows:
        s = r["strategy"]
        token_sums[s] = token_sums.get(s, 0) + r["token_count"]
        token_counts_by_strategy[s] = token_counts_by_strategy.get(s, 0) + 1

    print("\nIngestion verification:")
    print(f"  {'Strategy':<15} {'Count':>8} {'Avg Tokens':>12}")
    print(f"  {'-'*15} {'-'*8} {'-'*12}")
    found = set()
    for strategy in sorted(counts):
        count = counts[strategy]
        avg = token_sums[strategy] // token_counts_by_strategy[strategy]
        print(f"  {strategy:<15} {count:>8} {avg:>12}")
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
