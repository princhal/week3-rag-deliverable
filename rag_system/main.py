"""
main.py
-------
End-to-end RAG pipeline runner.

Stages (run in order or individually via --stage flag):
  1. extract   — extract text from PDF
  2. clean     — clean extracted text
  3. chunk     — apply 3 chunking strategies
  4. embed     — generate embeddings and ingest to Supabase
  5. query     — run 10 semantic queries
  6. evaluate  — compute metrics and produce markdown table

Usage:
  python main.py --pdf data/source.pdf               # full pipeline
  python main.py --pdf data/source.pdf --stage chunk # single stage
  python main.py --stage query                       # resume from query
  python main.py --stage evaluate                    # just re-run evaluation
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = "data"
RESULTS_DIR = "results"


def stage_extract(pdf_path: str) -> None:
    print("\n" + "=" * 60)
    print("STAGE 1: PDF Extraction")
    print("=" * 60)
    from src.extract import extract_pdf
    extract_pdf(pdf_path, DATA_DIR)


def stage_clean() -> None:
    print("\n" + "=" * 60)
    print("STAGE 2: Text Cleaning")
    print("=" * 60)
    from src.clean import load_cleaned_text, clean_text
    raw_text_path = Path(DATA_DIR) / "raw_text.txt"
    if not raw_text_path.exists():
        print("ERROR: raw_text.txt not found. Run --stage extract first.")
        sys.exit(1)
    raw_text = raw_text_path.read_text(encoding="utf-8")
    clean_text(raw_text, DATA_DIR)


def stage_chunk(pdf_path: str) -> None:
    print("\n" + "=" * 60)
    print("STAGE 3: Chunking (3 strategies)")
    print("=" * 60)
    from src.clean import load_cleaned_text
    from src.chunk import run_all_strategies
    cleaned_text, page_offsets = load_cleaned_text(DATA_DIR)
    source_doc = Path(pdf_path).name if pdf_path else "source.pdf"
    run_all_strategies(cleaned_text, page_offsets, source_doc, DATA_DIR)


def stage_embed() -> None:
    print("\n" + "=" * 60)
    print("STAGE 4: Embedding + Ingestion")
    print("=" * 60)
    import json
    from src.embed import embed_and_ingest, verify_ingestion
    chunks_path = Path(DATA_DIR) / "chunks.json"
    if not chunks_path.exists():
        print("ERROR: chunks.json not found. Run --stage chunk first.")
        sys.exit(1)
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    embed_and_ingest(chunks, DATA_DIR)
    verify_ingestion()


def stage_query() -> None:
    print("\n" + "=" * 60)
    print("STAGE 5: Query Execution")
    print("=" * 60)
    queries_path = Path(DATA_DIR) / "queries.json"
    if not queries_path.exists():
        # Fall back to template with a clear message
        template_path = Path(DATA_DIR) / "queries_template.json"
        if template_path.exists():
            print(f"WARNING: queries.json not found.")
            print(f"  Copy {template_path} to {queries_path},")
            print("  fill in actual query text and gold_char_start/gold_char_end values,")
            print("  then re-run this stage.")
        else:
            print("ERROR: queries.json not found in data/. Create it from queries_template.json.")
        sys.exit(1)
    from src.query import run_queries
    run_queries(str(queries_path), RESULTS_DIR)


def stage_evaluate() -> None:
    print("\n" + "=" * 60)
    print("STAGE 6: Evaluation + Markdown Table")
    print("=" * 60)
    raw_results_path = Path(RESULTS_DIR) / "raw_results.json"
    if not raw_results_path.exists():
        print("ERROR: raw_results.json not found. Run --stage query first.")
        sys.exit(1)
    from src.evaluate import evaluate
    evaluate(str(raw_results_path), RESULTS_DIR)
    print(f"\nDone. Open results/retrieval_comparison.md to view the comparison table.")


STAGES = {
    "extract":  stage_extract,
    "clean":    stage_clean,
    "chunk":    stage_chunk,
    "embed":    stage_embed,
    "query":    stage_query,
    "evaluate": stage_evaluate,
}

STAGE_ORDER = ["extract", "clean", "chunk", "embed", "query", "evaluate"]


def main():
    parser = argparse.ArgumentParser(
        description="RAG pipeline: PDF → chunks → embeddings → Supabase → evaluation"
    )
    parser.add_argument(
        "--pdf", type=str, default=None,
        help="Path to source PDF file (required for extract/chunk stages)"
    )
    parser.add_argument(
        "--stage", type=str, default=None,
        choices=list(STAGES.keys()),
        help="Run a single stage only. Omit to run full pipeline."
    )
    parser.add_argument(
        "--from-stage", type=str, default=None,
        choices=list(STAGES.keys()),
        help="Resume pipeline from this stage onwards."
    )
    args = parser.parse_args()

    # Resolve PDF path from args or environment
    pdf_path = args.pdf or os.environ.get("PDF_PATH")

    # Determine which stages to run
    if args.stage:
        stages_to_run = [args.stage]
    elif args.from_stage:
        start_idx = STAGE_ORDER.index(args.from_stage)
        stages_to_run = STAGE_ORDER[start_idx:]
    else:
        stages_to_run = STAGE_ORDER

    # Validate PDF is provided where needed
    pdf_required_stages = {"extract", "chunk"}
    needs_pdf = any(s in pdf_required_stages for s in stages_to_run)
    if needs_pdf and not pdf_path:
        print("ERROR: --pdf <path> is required for extract and chunk stages.")
        print("  Set PDF_PATH in .env or pass --pdf <path>")
        sys.exit(1)

    print(f"RAG Pipeline — running stages: {', '.join(stages_to_run)}")
    if pdf_path:
        print(f"  PDF: {pdf_path}")

    for stage_name in stages_to_run:
        fn = STAGES[stage_name]
        # Stages that need pdf_path
        if stage_name in ("extract", "chunk"):
            fn(pdf_path)
        else:
            fn()

    print("\n" + "=" * 60)
    print("Pipeline complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
