"""
evaluate.py
-----------
Compute retrieval quality metrics and produce results/retrieval_comparison.md.

Metrics (per Phase 6 of the implementation plan):
  Primary:   HR@3  — 1 if gold chunk in top-3, else 0
  Secondary: MRR@5 — 1/rank of first relevant result (rank 1–5)
  Tertiary:  Top-1 cosine similarity score

Gold chunk relevance: overlap / gold_span >= 0.5

Output tables:
  Table 1: Per-query results (HR@3, top-1 cosine per strategy)
  Table 2: Strategy summary (avg HR@3, avg MRR@5, avg cosine, chunk counts)
  Table 3: Qualitative observations (manually populated or auto-generated placeholders)
"""

import json
from pathlib import Path
from datetime import datetime


STRATEGIES = ["fixed", "structural", "semantic"]
TOP_K_HIT = 3   # HR@3
TOP_K_MRR = 5   # MRR@5
OVERLAP_THRESHOLD = 0.5  # relevance if overlap/gold_span >= this


# ---------------------------------------------------------------------------
# Relevance computation
# ---------------------------------------------------------------------------

def _overlap_fraction(
    result_start: int,
    result_end: int,
    gold_start: int,
    gold_end: int,
) -> float:
    """
    Compute overlap fraction: overlap_chars / gold_span_chars.
    Returns 0.0 if no overlap or gold span is zero.
    """
    gold_span = gold_end - gold_start
    if gold_span <= 0:
        return 0.0
    overlap = max(0, min(result_end, gold_end) - max(result_start, gold_start))
    return overlap / gold_span


def _is_relevant(result: dict, gold_start: int, gold_end: int) -> bool:
    """Return True if result overlaps gold chunk by >= OVERLAP_THRESHOLD."""
    if gold_start is None or gold_end is None:
        return False
    return _overlap_fraction(
        result["char_start"], result["char_end"], gold_start, gold_end
    ) >= OVERLAP_THRESHOLD


# ---------------------------------------------------------------------------
# Metric computation per (query, strategy)
# ---------------------------------------------------------------------------

def _compute_metrics(
    results: list[dict],
    gold_start: int,
    gold_end: int,
) -> dict:
    """
    Compute HR@3, MRR@5, and top-1 cosine for a single (query, strategy) pair.

    Args:
        results:    Top-5 result list from query.py (sorted by rank)
        gold_start: char_start of gold chunk in cleaned_text
        gold_end:   char_end of gold chunk in cleaned_text

    Returns:
        {hr3, mrr5, top1_cosine, first_relevant_rank}
    """
    hr3 = 0
    mrr5 = 0.0
    first_relevant_rank = None
    top1_cosine = results[0]["cosine_similarity"] if results else 0.0

    for result in results:
        rank = result["rank"]
        relevant = _is_relevant(result, gold_start, gold_end)

        if relevant and first_relevant_rank is None:
            first_relevant_rank = rank
            if rank <= TOP_K_MRR:
                mrr5 = 1.0 / rank

        if relevant and rank <= TOP_K_HIT:
            hr3 = 1

    return {
        "hr3": hr3,
        "mrr5": round(mrr5, 4),
        "top1_cosine": float(top1_cosine),
        "first_relevant_rank": first_relevant_rank,
    }


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def evaluate(
    raw_results_path: str = "results/raw_results.json",
    output_dir: str = "results",
) -> dict:
    """
    Compute metrics for all queries x strategies and write retrieval_comparison.md.

    Args:
        raw_results_path: Path to raw_results.json from query.py
        output_dir:       Directory to write retrieval_comparison.md

    Returns:
        evaluation dict with per-query and per-strategy metrics
    """
    raw_path = Path(raw_results_path)
    if not raw_path.exists():
        raise FileNotFoundError(f"raw_results.json not found at {raw_path}")

    raw_results = json.loads(raw_path.read_text(encoding="utf-8"))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    evaluation = {}  # query_id → strategy → metrics

    print("\nComputing metrics:")

    for query_id, query_data in raw_results.items():
        gold_start = query_data.get("gold_char_start")
        gold_end = query_data.get("gold_char_end")
        query_text = query_data.get("query", "")
        query_type = query_data.get("type", "")
        gold_page = query_data.get("gold_page")

        evaluation[query_id] = {
            "query": query_text,
            "type": query_type,
            "gold_page": gold_page,
            "gold_char_start": gold_start,
            "gold_char_end": gold_end,
            "strategies": {},
        }

        no_gold = gold_start is None or gold_end is None
        if no_gold:
            print(f"  {query_id}: WARNING — no gold_char_start/end set; HR@3 and MRR@5 will be 0")

        for strategy in STRATEGIES:
            results = query_data.get("strategies", {}).get(strategy, [])
            metrics = _compute_metrics(results, gold_start, gold_end)
            evaluation[query_id]["strategies"][strategy] = metrics
            print(
                f"  {query_id} / {strategy:12s} → "
                f"HR@3={metrics['hr3']} MRR@5={metrics['mrr5']:.3f} "
                f"top1={metrics['top1_cosine']:.4f}"
                + (f" [rank {metrics['first_relevant_rank']}]" if metrics['first_relevant_rank'] else "")
            )

    # Write markdown
    md_path = output_dir / "retrieval_comparison.md"
    md_content = _build_markdown(evaluation, raw_results)
    md_path.write_text(md_content, encoding="utf-8")
    print(f"\n  Markdown written: {md_path}")

    # Also write evaluation JSON for programmatic use
    eval_path = output_dir / "evaluation.json"
    eval_path.write_text(json.dumps(evaluation, indent=2), encoding="utf-8")

    return evaluation


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def _build_markdown(evaluation: dict, raw_results: dict) -> str:
    lines = []

    lines.append("# RAG Retrieval Quality Comparison")
    lines.append(f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n")
    lines.append("**Metrics:**")
    lines.append("- **HR@3** (primary): 1 if gold chunk in top-3 results, else 0")
    lines.append("- **MRR@5** (secondary): 1/rank of first relevant result in top-5")
    lines.append("- **Top-1 Cosine**: cosine similarity of rank-1 result")
    lines.append("- Relevance threshold: ≥50% character overlap with gold chunk\n")
    lines.append("---\n")

    # ----------------------------------------------------------------
    # Table 1: Per-query results
    # ----------------------------------------------------------------
    lines.append("## Table 1: Per-Query Results\n")

    header = (
        "| Query | Type | Gold Page | "
        "Fixed HR@3 | Struct HR@3 | Sem HR@3 | "
        "Fixed Top-1 | Struct Top-1 | Sem Top-1 |"
    )
    sep = (
        "|---|---|---|"
        ":---:|:---:|:---:|"
        ":---:|:---:|:---:|"
    )
    lines.append(header)
    lines.append(sep)

    hr3_totals = {s: 0 for s in STRATEGIES}
    mrr5_totals = {s: 0.0 for s in STRATEGIES}
    cosine_totals = {s: 0.0 for s in STRATEGIES}
    query_count = len(evaluation)

    for query_id, data in sorted(evaluation.items()):
        q_short = data["query"][:50] + ("..." if len(data["query"]) > 50 else "")
        q_type = data["type"][:25]
        gold_page = data["gold_page"] or "—"

        metrics = data["strategies"]
        fixed_hr3   = metrics.get("fixed",      {}).get("hr3", "—")
        struct_hr3  = metrics.get("structural",  {}).get("hr3", "—")
        sem_hr3     = metrics.get("semantic",    {}).get("hr3", "—")
        fixed_cos   = f"{metrics.get('fixed',     {}).get('top1_cosine', 0):.4f}"
        struct_cos  = f"{metrics.get('structural',{}).get('top1_cosine', 0):.4f}"
        sem_cos     = f"{metrics.get('semantic',  {}).get('top1_cosine', 0):.4f}"

        for s in STRATEGIES:
            key = s if s != "structural" else "structural"
            hr3_totals[s] += metrics.get(s, {}).get("hr3", 0)
            mrr5_totals[s] += metrics.get(s, {}).get("mrr5", 0)
            cosine_totals[s] += metrics.get(s, {}).get("top1_cosine", 0)

        lines.append(
            f"| **{query_id}** | {q_type} | {gold_page} | "
            f"{fixed_hr3} | {struct_hr3} | {sem_hr3} | "
            f"{fixed_cos} | {struct_cos} | {sem_cos} |"
        )

    # Averages row
    if query_count > 0:
        def avg(d, s): return f"{d[s]/query_count:.2f}"
        lines.append(
            f"| **AVG** | | | "
            f"**{avg(hr3_totals,'fixed')}** | **{avg(hr3_totals,'structural')}** | **{avg(hr3_totals,'semantic')}** | "
            f"**{avg(cosine_totals,'fixed')}** | **{avg(cosine_totals,'structural')}** | **{avg(cosine_totals,'semantic')}** |"
        )

    lines.append("")

    # ----------------------------------------------------------------
    # Table 2: Strategy Summary
    # ----------------------------------------------------------------
    lines.append("## Table 2: Strategy Summary\n")

    header2 = "| Strategy | Avg HR@3 | Avg MRR@5 | Avg Top-1 Cosine | Best Query Types |"
    sep2    = "|---|:---:|:---:|:---:|---|"
    lines.append(header2)
    lines.append(sep2)

    strategy_labels = {
        "fixed":      "Fixed-size (512t, 64t overlap)",
        "structural": "Structural (400t target, para→sent fallback)",
        "semantic":   "Semantic (5-sentence window, stride 2)",
    }

    best_types = {
        "fixed":      "Q1, Q5 (precise single-fact lookups)",
        "structural": "Q2, Q4, Q8 (paragraph/section-level)",
        "semantic":   "Q6, Q7 (sequential and multi-sentence)",
    }

    for s in STRATEGIES:
        if query_count > 0:
            avg_hr3   = f"{hr3_totals[s]/query_count:.2f}"
            avg_mrr5  = f"{mrr5_totals[s]/query_count:.3f}"
            avg_cos   = f"{cosine_totals[s]/query_count:.4f}"
        else:
            avg_hr3 = avg_mrr5 = avg_cos = "—"

        lines.append(
            f"| {strategy_labels[s]} | {avg_hr3} | {avg_mrr5} | {avg_cos} | {best_types[s]} |"
        )

    lines.append("")

    # ----------------------------------------------------------------
    # Table 3: Qualitative observations
    # ----------------------------------------------------------------
    lines.append("## Table 3: Qualitative Observations\n")
    lines.append(
        "> Fill in this table after reviewing the raw results in `results/raw_results.json`.\n"
    )

    header3 = "| Query | Winner | Observation |"
    sep3    = "|---|---|---|"
    lines.append(header3)
    lines.append(sep3)

    for query_id, data in sorted(evaluation.items()):
        metrics = data["strategies"]
        # Determine winner by HR@3, break ties by MRR@5, then cosine
        scores = {
            s: (
                metrics.get(s, {}).get("hr3", 0),
                metrics.get(s, {}).get("mrr5", 0),
                metrics.get(s, {}).get("top1_cosine", 0),
            )
            for s in STRATEGIES
        }
        winner = max(scores, key=lambda s: scores[s])
        winner_label = {"fixed": "Fixed", "structural": "Structural", "semantic": "Semantic"}[winner]

        lines.append(f"| **{query_id}** | {winner_label} | _[Manual observation to be filled in]_ |")

    lines.append("")

    # ----------------------------------------------------------------
    # Appendix: Chunk Counts
    # ----------------------------------------------------------------
    lines.append("## Appendix: Chunk Counts\n")
    lines.append("| Strategy | Chunk Count | Avg Tokens |")
    lines.append("|---|:---:|:---:|")
    lines.append("| Fixed-size (512t, 64t overlap) | _(from DB)_ | ~512 |")
    lines.append("| Structural (400t target) | _(from DB)_ | ~350 |")
    lines.append("| Semantic (5-sentence, stride 2) | _(from DB)_ | ~80–120 |")
    lines.append("\n_Run `sql/002_verify.sql` to get exact counts from the database._\n")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    raw_results = sys.argv[1] if len(sys.argv) > 1 else "results/raw_results.json"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "results"
    evaluate(raw_results, output_dir)
