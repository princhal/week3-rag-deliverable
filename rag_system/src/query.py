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

from dotenv import load_dotenv
from supabase import create_client, Client

from src.embed import _embed_query

load_dotenv()

STRATEGIES = ["fixed", "structural", "semantic"]
TOP_K = 5


def _get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(url, key)


def run_queries(
    queries_path: str = "data/queries.json",
    output_dir: str = "results",
) -> dict:
    queries_path = Path(queries_path)
    if not queries_path.exists():
        raise FileNotFoundError(f"queries.json not found at {queries_path}")

    queries = json.loads(queries_path.read_text(encoding="utf-8"))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    client = _get_supabase_client()
    raw_results = {}

    print(f"\nRunning {len(queries)} queries x {len(STRATEGIES)} strategies = "
          f"{len(queries) * len(STRATEGIES)} total retrievals\n")

    for q in queries:
        query_id = q["id"]
        query_text = q["query"]
        gold_char_start = q.get("gold_char_start")
        gold_char_end = q.get("gold_char_end")

        print(f"  {query_id}: {query_text[:70]}{'...' if len(query_text) > 70 else ''}")

        # Embed the query using RETRIEVAL_QUERY task type
        query_vector = _embed_query(query_text)

        raw_results[query_id] = {
            "query": query_text,
            "type": q.get("type", ""),
            "gold_char_start": gold_char_start,
            "gold_char_end": gold_char_end,
            "gold_page": q.get("gold_page"),
            "strategies": {},
        }

        for strategy in STRATEGIES:
            # Use Supabase RPC for vector similarity search
            response = client.rpc(
                "match_chunks",
                {
                    "query_embedding": query_vector,
                    "match_strategy": strategy,
                    "match_count": TOP_K,
                }
            ).execute()

            results = []
            for rank, row in enumerate(response.data or [], start=1):
                results.append({
                    "rank": rank,
                    "chunk_id": row.get("chunk_id"),
                    "source_page": row.get("source_page"),
                    "char_start": row.get("char_start"),
                    "char_end": row.get("char_end"),
                    "cosine_similarity": round(row.get("similarity", 0), 6),
                    "chunk_text_preview": (row.get("chunk_text", ""))[:200],
                    "chunk_text_full": row.get("chunk_text", ""),
                })

            raw_results[query_id]["strategies"][strategy] = results
            top1 = results[0]["cosine_similarity"] if results else 0.0
            print(f"    {strategy:12s} → top-1 cosine: {top1:.4f}")

    out_path = output_dir / "raw_results.json"
    out_path.write_text(json.dumps(raw_results, indent=2), encoding="utf-8")
    print(f"\n  Results written: {out_path}")

    return raw_results


if __name__ == "__main__":
    import sys
    queries_path = sys.argv[1] if len(sys.argv) > 1 else "data/queries.json"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "results"
    run_queries(queries_path, output_dir)
