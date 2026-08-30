"""
query.py
--------
Execute semantic queries against the document_chunks table for each strategy.
Produces results/raw_results.json with top-5 results per (query, strategy) pair.

Input:  data/queries.json      — list of query objects (see template)
Output: results/raw_results.json — nested dict: query_id → strategy → [top-5 results]
"""

import json
import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from src.embed import _embed_batch, _vector_to_pg

load_dotenv()

STRATEGIES = ["fixed", "structural", "semantic"]
TOP_K = 5

QUERY_SQL = """
SET hnsw.ef_search = 40;
SELECT
    chunk_id,
    strategy,
    source_page,
    char_start,
    char_end,
    chunk_text,
    ROUND((1 - (embedding <=> %s::vector))::numeric, 6) AS cosine_similarity
FROM document_chunks
WHERE strategy = %s
ORDER BY embedding <=> %s::vector
LIMIT %s;
"""


def _get_db_conn():
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise EnvironmentError("SUPABASE_DB_URL not set")
    return psycopg2.connect(db_url)


def run_queries(
    queries_path: str = "data/queries.json",
    output_dir: str = "results",
) -> dict:
    """
    For each query in queries.json, retrieve top-5 results from each strategy.

    Args:
        queries_path: Path to queries.json
        output_dir:   Directory to write raw_results.json

    Returns:
        raw_results dict: {query_id: {strategy: [result, ...]}}
    """
    queries_path = Path(queries_path)
    if not queries_path.exists():
        raise FileNotFoundError(f"queries.json not found at {queries_path}")

    queries = json.loads(queries_path.read_text(encoding="utf-8"))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = _get_db_conn()
    raw_results = {}

    print(f"\nRunning {len(queries)} queries x {len(STRATEGIES)} strategies = "
          f"{len(queries) * len(STRATEGIES)} total retrievals\n")

    for q in queries:
        query_id = q["id"]           # e.g. "Q1"
        query_text = q["query"]
        gold_char_start = q.get("gold_char_start")
        gold_char_end = q.get("gold_char_end")

        print(f"  {query_id}: {query_text[:70]}{'...' if len(query_text) > 70 else ''}")

        # Embed the query (single item batch)
        embeddings = _embed_batch([query_text])
        query_vector = _vector_to_pg(embeddings[0])

        raw_results[query_id] = {
            "query": query_text,
            "type": q.get("type", ""),
            "gold_char_start": gold_char_start,
            "gold_char_end": gold_char_end,
            "gold_page": q.get("gold_page"),
            "strategies": {},
        }

        for strategy in STRATEGIES:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # SET hnsw.ef_search must be a separate statement
                cur.execute("SET hnsw.ef_search = 40;")
                cur.execute(
                    """
                    SELECT
                        chunk_id,
                        strategy,
                        source_page,
                        char_start,
                        char_end,
                        chunk_text,
                        ROUND((1 - (embedding <=> %s::vector))::numeric, 6) AS cosine_similarity
                    FROM document_chunks
                    WHERE strategy = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                    """,
                    (query_vector, strategy, query_vector, TOP_K),
                )
                rows = cur.fetchall()

            results = []
            for rank, row in enumerate(rows, start=1):
                results.append({
                    "rank": rank,
                    "chunk_id": row["chunk_id"],
                    "source_page": row["source_page"],
                    "char_start": row["char_start"],
                    "char_end": row["char_end"],
                    "cosine_similarity": float(row["cosine_similarity"]),
                    "chunk_text_preview": row["chunk_text"][:200],
                    "chunk_text_full": row["chunk_text"],
                })

            raw_results[query_id]["strategies"][strategy] = results
            top1 = results[0]["cosine_similarity"] if results else 0.0
            print(f"    {strategy:12s} → top-1 cosine: {top1:.4f}")

    conn.close()

    # Write output
    out_path = output_dir / "raw_results.json"
    out_path.write_text(json.dumps(raw_results, indent=2), encoding="utf-8")
    print(f"\n  Results written: {out_path}")

    return raw_results


if __name__ == "__main__":
    import sys
    queries_path = sys.argv[1] if len(sys.argv) > 1 else "data/queries.json"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "results"
    run_queries(queries_path, output_dir)
