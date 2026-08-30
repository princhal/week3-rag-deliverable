# Meta-Prompting Playbook — W03 Data Pipeline (Supabase + pgvector RAG Comparison)

Three stages. Run each with an LLM (Claude chat for Stage 1 and 3, Claude Code for Stage 2). Paste the **output** of one stage into the **input** of the next.

---

## Stage 1 — Planning Meta-Prompt

Use this in a chat with an LLM first. Its job is to turn the deliverable into a concrete, decision-complete plan — no code yet.

```
You are a senior ML infrastructure engineer specializing in RAG systems and vector databases.

TASK: Produce a structured technical implementation plan for the deliverable below.
Do not write code. Make every design decision explicit and justify it — a developer
or coding agent should be able to execute your plan without guessing.

DELIVERABLE:
Set up Supabase with pgvector. Ingest a 50-page PDF with 3 chunking strategies,
generate embeddings, run 10 semantic queries. Produce a markdown comparison table
of retrieval quality across chunk sizes.

SUCCESS CRITERIA:
- Supabase pgvector configured with HNSW or IVFFlat index
- 3 chunking strategies implemented and compared
- 10 semantic queries with documented results
- Markdown comparison table of retrieval quality

Address each phase explicitly:

1. SCHEMA & INDEX
   - Table schema (columns, vector dimension, metadata fields: chunk_id, strategy,
     source_page, char_start/end)
   - HNSW vs IVFFlat — pick one for a single 50-page document and justify it
     (dataset size, recall/latency tradeoff, build cost)
   - Exact index parameters (e.g. HNSW: m, ef_construction; IVFFlat: lists)

2. INGESTION
   - PDF extraction library and approach (layout-aware vs raw text)
   - Cleaning steps (headers/footers, hyphenation, whitespace)

3. THREE CHUNKING STRATEGIES — define each precisely, with parameters:
   - Fixed-size with overlap (size + overlap in tokens/chars)
   - Structural/recursive (split on headings/paragraphs, target size, fallback rule)
   - Semantic/sentence-boundary (embedding-similarity or sentence-window based,
     with its threshold or window size)

4. EMBEDDINGS
   - Model choice + dimension, batching approach
   - How each embedding is tagged back to (chunk_id, strategy, source_page)

5. QUERY DESIGN
   - How to construct 10 queries that actually differentiate the strategies
     (mix of: single-fact lookup, multi-sentence/context-dependent, cross-section
     synthesis) rather than 10 generic questions

6. EVALUATION METHOD
   - Define "retrieval quality" precisely: e.g. top-k cosine similarity score,
     manual relevance rating (1-5) against a human-identified gold chunk, or
     hit-rate@k against a labeled answer location. Pick one primary metric and
     justify it given no pre-existing ground truth.
   - Exact procedure for turning 10 queries x 3 strategies into one markdown table

7. CHECKLIST — map every item above back to the 4 success criteria, 1:1.

Output as structured markdown with one header per phase. Flag every assumption
you make as "ASSUMPTION:" inline.
```

**What you get back:** a decision-complete spec (index type + params, 3 chunking definitions with real numbers, the metric you'll score with). Sanity-check it against the cheat sheet at the bottom of this doc before moving on.

---

## Stage 2 — Build Meta-Prompt

Use this with a coding agent (Claude Code is a good fit for this — see note below). Paste Stage 1's output where marked.

```
You are implementing the plan below in Python, incrementally. Verify each phase
before moving to the next — don't write all the code up front.

PLAN:
<<< PASTE STAGE 1 OUTPUT HERE >>>

ENVIRONMENT:
- Supabase project (SUPABASE_URL, SUPABASE_SERVICE_KEY as env vars)
- Python 3.11, supabase-py + psycopg2/asyncpg for direct SQL against pgvector
- Embedding library: <<< fill in, e.g. openai / sentence-transformers >>>

RULES:
- Real runnable code per phase, not pseudocode.
- After each phase, print a concrete verification: row counts after ingestion,
  confirmation the HNSW/IVFFlat index was created (query pg_indexes), embedding
  vector shape/dtype, etc. Don't proceed silently.
- Keep each chunking strategy in its own clearly named function/module so results
  stay attributable in the final comparison.
- At the end, emit results as a list of dicts:
  {query, strategy, retrieved_chunks: [...], scores: [...]}
  so Stage 3 can consume it directly.

Pause and ask me before Phase 5 (the 10 queries) — I want to review or supply
the actual questions rather than have you invent all of them.
```

---

## Stage 3 — Evaluation Meta-Prompt

Back in chat, once you have raw results.

```
You have raw retrieval results for 10 queries x 3 chunking strategies below.

RESULTS:
<<< PASTE RAW OUTPUT: retrieved chunks + scores per query per strategy >>>

METRIC: <<< the one you chose/justified in Stage 1, e.g. hit-rate@3 against a
gold chunk, or manual 1-5 relevance >>>

PRODUCE:
1. A markdown table — rows = 10 queries, columns = the 3 strategies, each cell =
   score + a one-line reason (not just a number).
2. A summary paragraph: which strategy won overall, and under what query type
   (factual lookup vs. multi-hop/synthesis) — tie the result to chunk
   size/boundary behavior, not just "strategy X scored higher."
3. A short "limitations" section: single document, single embedding model, no
   independently-verified gold labels, sample size of 10.
```

---

## Quick technical anchors (sanity-check the LLM's Stage 1 output against these)

- **HNSW vs IVFFlat**: for a single 50-page PDF (a few hundred chunks), HNSW is
  almost always the right call — it doesn't need a training/list-building step
  over a minimum row count the way IVFFlat does, and at this scale the memory
  overhead difference is negligible. IVFFlat only starts making sense once
  you're indexing hundreds of thousands+ of vectors.
- **Three chunking strategies people typically compare**: fixed-size w/ overlap
  (simple, size-controlled baseline), structural (heading/paragraph-aware,
  respects document semantics), and semantic/sentence-window (adaptive
  boundaries based on embedding similarity between adjacent sentences). Pick
  parameters that actually produce visibly different chunk counts — e.g. ~200,
  ~500, ~1000 tokens — or the comparison table will show noise, not signal.
- **Without ground-truth labels**, the honest metric is either (a) you manually
  identify which chunk *should* answer each of your 10 queries before running
  anything, then measure hit-rate@k, or (b) top-1 cosine similarity score as a
  proxy — weaker, but defensible if you say so explicitly.
