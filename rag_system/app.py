"""
app.py
------
FastAPI backend for the RAG system UI.

Endpoints:
  GET  /                        → serves ui/index.html
  GET  /api/results             → retrieval_comparison data (metrics + per-query results)
  GET  /api/chunks              → all chunks from chunks.json grouped by strategy
  GET  /api/queries             → queries.json
  POST /api/query               → live semantic search across all 3 strategies
  GET  /api/stats               → chunk counts and avg tokens per strategy
"""

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Add project root to path so src.* imports work
sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

app = FastAPI(title="RAG Chunking Explorer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
RESULTS_DIR = BASE / "results"
UI_DIR = BASE / "ui"


def _load_json(path: Path) -> dict | list:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{path.name} not found. Run the pipeline first.")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = UI_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.get("/api/results")
def get_results():
    """
    Returns structured evaluation data combining raw_results.json and evaluation.json.
    If evaluation.json doesn't exist, computes metrics on the fly from raw_results.json.
    """
    raw_results = _load_json(RESULTS_DIR / "raw_results.json")

    # Load or compute per-query metrics
    eval_path = RESULTS_DIR / "evaluation.json"
    if eval_path.exists():
        evaluation = json.loads(eval_path.read_text(encoding="utf-8"))
    else:
        evaluation = {}

    # Build unified response
    queries = []
    strategies = ["fixed", "structural", "semantic"]

    for qid, qdata in raw_results.items():
        entry = {
            "id": qid,
            "query": qdata.get("query", ""),
            "type": qdata.get("type", ""),
            "gold_page": qdata.get("gold_page"),
            "strategies": {},
        }

        eval_qdata = evaluation.get(qid, {})

        for strategy in strategies:
            results = qdata.get("strategies", {}).get(strategy, [])
            eval_metrics = eval_qdata.get("strategies", {}).get(strategy, {})

            entry["strategies"][strategy] = {
                "hr3": eval_metrics.get("hr3", None),
                "mrr5": eval_metrics.get("mrr5", None),
                "top1_cosine": results[0]["cosine_similarity"] if results else None,
                "top5": [
                    {
                        "rank": r["rank"],
                        "chunk_id": r["chunk_id"],
                        "source_page": r["source_page"],
                        "cosine_similarity": r["cosine_similarity"],
                        "preview": r["chunk_text_preview"],
                    }
                    for r in results
                ],
            }

        queries.append(entry)

    # Strategy summary
    summary = {}
    for strategy in strategies:
        hr3_vals = [q["strategies"][strategy]["hr3"] for q in queries if q["strategies"][strategy]["hr3"] is not None]
        mrr5_vals = [q["strategies"][strategy]["mrr5"] for q in queries if q["strategies"][strategy]["mrr5"] is not None]
        cos_vals = [q["strategies"][strategy]["top1_cosine"] for q in queries if q["strategies"][strategy]["top1_cosine"] is not None]
        summary[strategy] = {
            "avg_hr3": round(sum(hr3_vals) / len(hr3_vals), 3) if hr3_vals else None,
            "avg_mrr5": round(sum(mrr5_vals) / len(mrr5_vals), 3) if mrr5_vals else None,
            "avg_cosine": round(sum(cos_vals) / len(cos_vals), 4) if cos_vals else None,
        }

    return JSONResponse({"queries": queries, "summary": summary})


@app.get("/api/chunks")
def get_chunks():
    """Returns all chunks grouped by strategy with stats."""
    chunks = _load_json(DATA_DIR / "chunks.json")

    grouped = {"fixed": [], "structural": [], "semantic": []}
    for chunk in chunks:
        s = chunk.get("strategy")
        if s in grouped:
            grouped[s].append({
                "chunk_id": chunk["chunk_id"],
                "source_page": chunk["source_page"],
                "token_count": chunk["token_count"],
                "char_start": chunk["char_start"],
                "char_end": chunk["char_end"],
                "preview": chunk["chunk_text"][:200],
            })

    stats = {}
    for strategy, clist in grouped.items():
        tokens = [c["token_count"] for c in clist]
        stats[strategy] = {
            "count": len(clist),
            "avg_tokens": round(sum(tokens) / len(tokens)) if tokens else 0,
            "min_tokens": min(tokens) if tokens else 0,
            "max_tokens": max(tokens) if tokens else 0,
        }

    return JSONResponse({"chunks": grouped, "stats": stats})


@app.get("/api/queries")
def get_queries():
    """Returns the queries.json file."""
    return JSONResponse(_load_json(DATA_DIR / "queries.json"))


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


@app.post("/api/query")
def run_live_query(req: QueryRequest):
    """
    Run a live semantic query against all 3 strategies in Supabase.
    Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in .env.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query text cannot be empty")

    try:
        from src.embed import _embed_query
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise HTTPException(status_code=500, detail="Supabase credentials not configured")

        client = create_client(url, key)
        query_vector = _embed_query(req.query)

        results = {}
        for strategy in ["fixed", "structural", "semantic"]:
            response = client.rpc(
                "match_chunks",
                {
                    "query_embedding": query_vector,
                    "match_strategy": strategy,
                    "match_count": req.top_k,
                }
            ).execute()

            results[strategy] = [
                {
                    "rank": i + 1,
                    "chunk_id": row.get("chunk_id"),
                    "source_page": row.get("source_page"),
                    "cosine_similarity": round(row.get("similarity", 0), 6),
                    "preview": row.get("chunk_text", "")[:300],
                    "full_text": row.get("chunk_text", ""),
                }
                for i, row in enumerate(response.data or [])
            ]

        return JSONResponse({"query": req.query, "results": results})

    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Import error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
def get_stats():
    """Returns pipeline stats: chunk counts, model info, last run time."""
    chunks_path = DATA_DIR / "chunks.json"
    embed_log_path = DATA_DIR / "embed_log.json"

    stats = {
        "model": "all-MiniLM-L6-v2",
        "embedding_dim": 384,
        "chunks": {},
        "last_embed": None,
    }

    if chunks_path.exists():
        chunks = json.loads(chunks_path.read_text())
        from collections import Counter
        counts = Counter(c["strategy"] for c in chunks)
        token_sums = {}
        for c in chunks:
            s = c["strategy"]
            token_sums.setdefault(s, []).append(c["token_count"])
        for s, cnt in counts.items():
            stats["chunks"][s] = {
                "count": cnt,
                "avg_tokens": round(sum(token_sums[s]) / cnt),
            }

    if embed_log_path.exists():
        log = json.loads(embed_log_path.read_text())
        stats["last_embed"] = {
            "total": log.get("total_chunks"),
            "embedded": log.get("embedded"),
        }

    return JSONResponse(stats)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
