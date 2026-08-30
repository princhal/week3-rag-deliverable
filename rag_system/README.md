# RAG System: Supabase pgvector + PDF Chunking Comparison

End-to-end RAG pipeline that ingests a 50-page PDF using 3 chunking strategies,
generates OpenAI embeddings, stores them in Supabase pgvector, runs 10 semantic
queries, and produces a markdown comparison table of retrieval quality.

---

## Project Structure

```
rag_system/
├── main.py                    # End-to-end pipeline runner
├── requirements.txt           # Pinned Python dependencies
├── .env.example               # Environment variable template
├── src/
│   ├── extract.py             # PDF extraction (pdfplumber)
│   ├── clean.py               # Text cleaning pipeline
│   ├── chunk.py               # 3 chunking strategies
│   ├── embed.py               # OpenAI embeddings + Supabase ingestion
│   ├── query.py               # Semantic query execution
│   └── evaluate.py            # Metrics + markdown table generation
├── sql/
│   ├── 001_schema.sql         # Table schema + HNSW index
│   ├── 002_verify.sql         # Post-setup verification queries
│   └── 003_reset.sql          # Teardown script
├── data/
│   ├── queries_template.json  # Query template (copy → queries.json and fill in)
│   └── source.pdf             # Place your PDF here
└── results/
    ├── raw_results.json       # Top-5 results per query/strategy (auto-generated)
    ├── evaluation.json        # Computed metrics (auto-generated)
    └── retrieval_comparison.md # Final comparison table (auto-generated)
```

---

## Setup

### 1. Install dependencies

```bash
cd rag_system
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `SUPABASE_URL` — from Supabase dashboard → Project Settings → API
- `SUPABASE_DB_URL` — from Supabase dashboard → Project Settings → Database → Connection string (URI mode)
- `OPENAI_API_KEY` — your OpenAI API key
- `PDF_PATH` — path to your PDF file (e.g. `data/source.pdf`)

### 3. Set up Supabase schema

Run `sql/001_schema.sql` in the Supabase SQL editor (Dashboard → SQL Editor → New query):

```sql
-- paste contents of sql/001_schema.sql
```

Verify with `sql/002_verify.sql` — confirm pgvector ≥ 0.5.0 and HNSW index exists.

---

## Running the Pipeline

### Full pipeline (all stages)

```bash
python main.py --pdf data/source.pdf
```

### Individual stages

```bash
python main.py --pdf data/source.pdf --stage extract   # Stage 1: extract text
python main.py --stage clean                           # Stage 2: clean text
python main.py --pdf data/source.pdf --stage chunk     # Stage 3: chunk (3 strategies)
python main.py --stage embed                           # Stage 4: embed + ingest
python main.py --stage query                           # Stage 5: run queries
python main.py --stage evaluate                        # Stage 6: metrics + table
```

### Resume from a stage

```bash
python main.py --from-stage query   # run query + evaluate only
```

---

## Queries Setup (Required Before Stage 5)

Before running `--stage query`, you must:

1. Copy the template:
   ```bash
   cp data/queries_template.json data/queries.json
   ```

2. Open `data/queries.json` and for each of the 10 queries:
   - Replace `[REPLACE: ...]` placeholders with actual content from your PDF
   - Set `gold_page`, `gold_char_start`, and `gold_char_end` for each query
     (find these by reading `data/cleaned_text.txt` after running stages 1–2)

> **Why gold chunks matter:** HR@3 and MRR@5 are computed against gold chunk
> character offsets. Without them, only cosine similarity scores are meaningful.

---

## Chunking Strategies

| Strategy | Parameters | Expected Chunks |
|---|---|---|
| **Fixed-size** | 512 tokens, 64-token overlap | ~45 |
| **Structural** | 400-token target, paragraph→sentence fallback | ~40 |
| **Semantic** | 5-sentence window, stride 2 (60% overlap) | ~1,000–1,500 |

---

## Evaluation Metrics

| Metric | Definition | Primary? |
|---|---|---|
| **HR@3** | 1 if gold chunk in top-3 results | ✅ Primary |
| **MRR@5** | 1/rank of first relevant result | Secondary |
| **Top-1 Cosine** | Cosine similarity of rank-1 result | Tertiary |

Relevance: ≥50% character overlap between retrieved chunk and gold chunk.

---

## Output

After running all stages, `results/retrieval_comparison.md` contains:

- **Table 1**: Per-query HR@3, MRR@5, and top-1 cosine for each strategy
- **Table 2**: Strategy summary with averages and best query types
- **Table 3**: Qualitative observations (fill in manually after reviewing results)

---

## Assumptions

See `rag_implementation_plan.md` for the full assumption log. Key ones:

- pgvector ≥ 0.5.0 in Supabase (HNSW requires this)
- PDF is text-based (not scanned) — if scanned, add pytesseract OCR step
- OpenAI API key with access to `text-embedding-3-small`
- English-language PDF with standard sentence structure

---

## Re-running

The pipeline is idempotent:
- Chunks upsert on `chunk_id` conflict — safe to re-run embed stage
- `raw_results.json` and `retrieval_comparison.md` are overwritten each run
- Use `sql/003_reset.sql` to wipe the database and start fresh
