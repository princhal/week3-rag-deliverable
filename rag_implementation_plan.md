# RAG System: Technical Implementation Plan
### Supabase + pgvector · PDF Ingestion · 3 Chunking Strategies · Retrieval Quality Comparison

---

## Phase 1 — Schema & Index

### 1.1 Table Schema

Create one table that stores every chunk regardless of strategy, using a `strategy` discriminator column so all strategies can be queried and compared from a single relation.

```sql
-- Enable the extension (run once in Supabase SQL editor)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
    id              BIGSERIAL PRIMARY KEY,
    chunk_id        TEXT        NOT NULL UNIQUE,   -- format: <strategy>_<page>_<seq>
    strategy        TEXT        NOT NULL,           -- 'fixed', 'structural', 'semantic'
    source_doc      TEXT        NOT NULL,           -- filename of the source PDF
    source_page     SMALLINT    NOT NULL,           -- 1-based page number where chunk starts
    char_start      INTEGER     NOT NULL,           -- character offset in cleaned full-text
    char_end        INTEGER     NOT NULL,           -- character offset end (exclusive)
    token_count     SMALLINT    NOT NULL,           -- token count per tiktoken cl100k_base
    chunk_text      TEXT        NOT NULL,           -- raw chunk text for inspection/display
    embedding       VECTOR(1536) NOT NULL,          -- dimension matches text-embedding-3-small
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Column justifications:**
- `chunk_id` as a formatted string (`fixed_p04_003`) makes it human-readable in result tables without needing joins.
- `char_start / char_end` are offsets into the *cleaned* full-text string (post-normalization), not the raw PDF bytes, so they remain stable across runs.
- `token_count` is stored for post-hoc analysis (e.g. chunks that exceed context limits).
- `embedding VECTOR(1536)` matches the chosen model output (see Phase 4).

ASSUMPTION: The source PDF is a single document. `source_doc` is a constant value but is included for schema extensibility.

---

### 1.2 Index Choice: HNSW

**Decision: Use HNSW.** Do not use IVFFlat for this workload.

| Criterion | HNSW | IVFFlat |
|---|---|---|
| Dataset size | Works well at any size; excels on small-to-medium | Requires enough vectors to populate lists meaningfully; recommended minimum ~1k–10k per list |
| Recall | Near-exact at default params | Lower recall unless `ef_search` / `nprobe` are tuned; drops further on small datasets |
| Build cost | Higher memory during build; acceptable for < 10k vectors | Requires a `CLUSTER` pass; simpler but less forgiving |
| Query latency | Sub-millisecond at this scale | Comparable, but tuning is more opaque |
| Maintenance | Index stays live on inserts | Requires periodic `VACUUM`/rebuild as vectors accumulate |

A 50-page PDF will produce roughly 200–600 chunks across all three strategies combined. IVFFlat's `lists` parameter is typically set to `sqrt(N)`, which would be ≈ 15–25 — too few for meaningful clustering. HNSW is strictly better here.

**HNSW Index Parameters:**

```sql
CREATE INDEX ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

- `m = 16`: number of bi-directional links per node. Default is 16. Increasing to 32 improves recall marginally but doubles index size — unnecessary at this scale.
- `ef_construction = 64`: size of the dynamic candidate list during build. Default is 64. Higher values improve index quality at build time; 64 is sufficient for < 1k vectors.
- `vector_cosine_ops`: cosine similarity is the standard metric for OpenAI embeddings (they are unit-normalized, so cosine = dot product in practice).

**Query-time setting** (set per-session before queries):
```sql
SET hnsw.ef_search = 40;
```
`ef_search = 40` (default is 40) controls recall vs. latency at query time. For a dataset this small, the default is adequate. Raise to 80 if you observe recall degradation.

ASSUMPTION: pgvector version ≥ 0.5.0 is installed in the Supabase project (HNSW was added in 0.5.0). Verify with `SELECT extversion FROM pg_extension WHERE extname = 'vector';`.

---

## Phase 2 — Ingestion

### 2.1 PDF Extraction Library

**Use `pdfplumber`** (Python), not PyPDF2 or pdfminer directly.

Justification:
- `pdfplumber` exposes character-level bounding boxes, which lets you detect multi-column layout, headers, and footers by their y-position without resorting to regex heuristics alone.
- It returns text with explicit page boundaries and preserves reading order better than raw `pdfminer` for single-column academic/report PDFs.
- PyMuPDF (fitz) is a valid alternative with faster extraction, but `pdfplumber`'s table and layout awareness is more useful for cleaning.

ASSUMPTION: The PDF is text-based (not a scanned image). If OCR is needed, add `pytesseract` + `pdf2image` as a pre-processing step before `pdfplumber`.

**Extraction approach:**
1. Open the PDF with `pdfplumber`.
2. For each page, extract text via `page.extract_text(layout=True)`. The `layout=True` flag uses character positions to reconstruct reading order.
3. Tag each extracted string with its `page_number` (1-based).
4. Concatenate all pages into a single `full_text` string, inserting a page-boundary sentinel: `\n\n<<<PAGE_BREAK:N>>>\n\n` between pages. This sentinel is used downstream to recover `source_page` for any chunk.

---

### 2.2 Cleaning Steps

Apply cleaning in this exact order after extraction:

1. **Strip running headers/footers**: Detect lines that repeat across ≥ 80% of pages (e.g. document title, page numbers). Remove them. Implementation: collect the first and last 2 lines of each page's text; count line frequency across pages; remove any line appearing on > 40 of 50 pages.

2. **Dehyphenation**: Rejoin words split across line breaks with a hyphen. Pattern: `(\w+)-\n(\w+)` → `\1\2`. Apply before any other whitespace normalization.

3. **Normalize whitespace**: Replace sequences of 3+ newlines with exactly 2 newlines (paragraph boundary). Replace single newlines mid-paragraph with a space (continuation). Detect paragraph boundaries as double-newlines `\n\n`.

4. **Remove page-break artifacts**: Strip page numbers that appear as isolated integers on their own line (pattern: `^\s*\d{1,3}\s*$`).

5. **Unicode normalization**: Apply `unicodedata.normalize('NFKC', text)` to resolve ligatures (ﬁ → fi), smart quotes, and non-breaking spaces.

6. **Preserve page markers**: The `<<<PAGE_BREAK:N>>>` sentinels inserted in step 2.1 survive all cleaning steps — they are not whitespace-normalized. They will be stripped only after `char_start/char_end` offsets are computed.

After cleaning, store the cleaned full-text as a single string. All `char_start/char_end` values in the database reference offsets into this cleaned string.

---

## Phase 3 — Three Chunking Strategies

### Strategy A: Fixed-Size with Overlap

**Parameters:**
- Chunk size: **512 tokens**
- Overlap: **64 tokens** (12.5% of chunk size)
- Tokenizer: `tiktoken` with `cl100k_base` encoding (matches `text-embedding-3-small`)
- Unit: tokens (not characters), because the embedding model has a token limit and token counts are stable across character-level variation.

**Procedure:**
1. Tokenize the entire cleaned full-text into a token list using `tiktoken.get_encoding("cl100k_base")`.
2. Slide a window of 512 tokens with a step of 448 tokens (512 − 64).
3. Decode each window back to text.
4. Compute `char_start` / `char_end` by mapping token boundaries back to character offsets.
5. Determine `source_page` as the page containing the character at `char_start` (look up the nearest `<<<PAGE_BREAK:N>>>` sentinel).
6. Assign `chunk_id = "fixed_pNN_SSS"` (page, sequence).

**Expected chunk count**: For a 50-page document averaging 300 words/page (~400 tokens/page), total ≈ 20,000 tokens → ≈ 45 chunks.

ASSUMPTION: The cleaned document is ≤ 100,000 tokens (fits in a single tokenization pass in memory).

---

### Strategy B: Structural / Recursive

**Parameters:**
- Primary split: double newline `\n\n` (paragraph boundary)
- Secondary split (fallback): single newline `\n` (line boundary within a dense paragraph)
- Tertiary split (fallback): sentence boundary via regex `(?<=[.!?])\s+` (period/bang/question followed by whitespace)
- Target chunk size: **400 tokens** (≈ 300 words; slightly smaller than fixed to respect structural units)
- Max chunk size: **600 tokens** hard cap (triggers fallback splits)
- Min chunk size: **50 tokens** — chunks below this are merged with their successor

**Procedure:**
1. Split cleaned full-text on `\n\n` to get paragraphs.
2. For each paragraph, count tokens. If ≤ 600 tokens, treat as a candidate chunk.
3. If a paragraph exceeds 600 tokens, apply the secondary split (`\n`) and re-evaluate.
4. If still exceeds 600 tokens, apply the tertiary split (sentence boundary).
5. Greedily merge consecutive candidate chunks while their combined token count ≤ 400 tokens. When adding the next chunk would exceed 400, finalize the current merged chunk and start a new one.
6. This produces chunks that respect paragraph and sentence structure while staying near the target size.
7. Compute `char_start`, `char_end`, `source_page` the same way as Strategy A.
8. Assign `chunk_id = "structural_pNN_SSS"`.

**Expected chunk count**: Structural splitting on a well-formatted document typically produces 20% fewer chunks than fixed-size but with higher variance in size.

ASSUMPTION: Headings in the PDF are formatted as short isolated lines (< 15 words). They will be treated as their own paragraph and merged into the following body paragraph unless the result exceeds 400 tokens.

---

### Strategy C: Semantic / Sentence-Window

**Parameters:**
- Base unit: individual sentences (extracted via `spaCy` `en_core_web_sm` sentence segmenter)
- Window size: **5 sentences** (the chunk is 5 consecutive sentences)
- Stride: **2 sentences** (overlap of 3 sentences between consecutive chunks; 60% overlap)
- This is a sliding-window approach, not an embedding-similarity-threshold approach.

**Why sliding window, not similarity-threshold clustering?**
Embedding-similarity clustering (e.g., grouping sentences by cosine similarity > θ) requires an embedding call per sentence before chunking — this adds latency and cost and is circular when the goal is to evaluate embedding quality. A sliding sentence-window is deterministic, interpretable, and has been shown in literature to improve recall for question-answering tasks because adjacent context is preserved.

ASSUMPTION: `spaCy`'s `en_core_web_sm` sentence segmenter correctly handles this PDF's sentence structure. If the PDF contains bullet lists or numbered items that span line breaks, a small post-processing step is needed to merge list items into a single "sentence" before windowing.

**Procedure:**
1. Run `spaCy` NLP on the full cleaned text to get a flat list of sentence spans.
2. Slide a window of 5 sentences with a stride of 2.
3. Each chunk = sentences[i : i+5] concatenated with a single space.
4. Compute `char_start` as the start of sentence[i], `char_end` as the end of sentence[i+4].
5. Determine `source_page` from `char_start`.
6. Assign `chunk_id = "semantic_pNN_SSS"`.

**Expected chunk count**: For ≈ 2,000–3,000 sentences in 50 pages, with stride 2: roughly 1,000–1,500 chunks. This is significantly larger than the other strategies.

ASSUMPTION: If token count of a 5-sentence window exceeds 512 tokens (embedding model limit), reduce window size to 3 sentences. Log any windows that exceeded the limit before reduction.

---

## Phase 4 — Embeddings

### 4.1 Model Choice

**Model: `text-embedding-3-small` (OpenAI)**
**Dimension: 1536**

Justification:
- 1536-dimension output; fits `VECTOR(1536)` in pgvector without truncation.
- As of 2024–2025, `text-embedding-3-small` offers a strong recall/cost tradeoff for English text, outperforming `text-embedding-ada-002` at lower cost.
- `text-embedding-3-large` (3072-dim) would require a schema change and offers marginal improvement for a 50-page document.
- No local model is used to avoid hardware variance affecting results. ASSUMPTION: An OpenAI API key is available in the environment as `OPENAI_API_KEY`.

---

### 4.2 Batching Approach

The OpenAI embeddings API accepts up to **2,048 inputs per request** and enforces a **300,000 tokens/min** rate limit on `text-embedding-3-small` (Tier 1).

**Batching procedure:**
1. Collect all chunks across all 3 strategies into a single list of `(chunk_id, strategy, chunk_text)` tuples.
2. Sort by strategy to allow easy re-association.
3. Group into batches of **100 chunks per API call** (conservative, well under the 2,048 limit; keeps payload size manageable).
4. For each batch, call `openai.embeddings.create(model="text-embedding-3-small", input=[...texts...])`.
5. The API response returns embeddings in the same order as inputs — re-associate by index position.
6. After each batch, insert rows into `document_chunks` via a bulk `INSERT` (not individual inserts). Use `psycopg2.extras.execute_values` or Supabase's `upsert` with the `chunk_id` as the conflict target.

**Retry logic**: Wrap each batch call with exponential backoff (max 3 retries) on HTTP 429 (rate limit) and HTTP 500.

---

### 4.3 Metadata Tagging

Every row inserted carries the full provenance chain:

| Field | Source |
|---|---|
| `chunk_id` | Generated during chunking (Strategy + page + sequence) |
| `strategy` | Set during chunking: `'fixed'`, `'structural'`, `'semantic'` |
| `source_page` | Resolved from `char_start` vs. `<<<PAGE_BREAK:N>>>` sentinels |
| `char_start` / `char_end` | Computed during chunking |
| `token_count` | Computed with `tiktoken` before embedding call |
| `embedding` | Returned by OpenAI API, stored as `VECTOR(1536)` |

The embedding call itself is **stateless** with respect to metadata — metadata is assembled before the API call, and the embedding result is joined back by list index. No metadata is passed to the embedding model.

---

## Phase 5 — Query Design

### Design Principle

Ten generic "what does the document say about X?" queries will not differentiate chunking strategies, because all strategies will likely retrieve *some* relevant chunk for any well-formed factual question. The queries must be designed to stress-test specific failure modes of each strategy:

| Query Type | What It Stresses |
|---|---|
| Single-fact lookup | Fixed-size chunking: the fact may be split across a boundary |
| Context-dependent (multi-sentence) | Semantic windowing: does adjacent context improve retrieval? |
| Cross-section synthesis | Structural chunking: does paragraph-level grouping surface the right section? |
| Definition query | All three: a definition is usually a single sentence or paragraph |
| Contrastive / comparative | Fixed-size may split the comparison; structural should capture it |

ASSUMPTION: The PDF is a non-fiction technical or academic document with clearly identifiable facts, definitions, comparisons, and section boundaries. If the PDF is a novel or creative work, this query taxonomy does not apply.

### The 10 Queries

Design these queries against the actual PDF content after reading it. The templates below define the **type** and **rationale**; replace bracketed text with actual content from the document.

| # | Query Template | Type | Strategy Stress Target |
|---|---|---|---|
| Q1 | "What is the definition of [core technical term introduced in the document]?" | Single-fact / definition | Fixed-size (definition may straddle a token boundary) |
| Q2 | "What are the three main components of [central system/framework described]?" | Multi-part fact | Structural (enumerations often span a paragraph) |
| Q3 | "How does [concept A] differ from [concept B]?" | Contrastive | All three — semantic window should capture contrast if co-located |
| Q4 | "What is the stated purpose of [methodology/approach] described in [section name]?" | Context-dependent (requires heading context) | Structural (heading provides context) |
| Q5 | "What specific numerical value or statistic is reported for [metric]?" | Single precise fact | Fixed-size (number may be surrounded by irrelevant context) |
| Q6 | "What step follows [action X] in the process described in [section]?" | Sequential/procedural | Semantic window (sequential steps benefit from neighbor sentences) |
| Q7 | "What limitations or caveats does the document mention for [approach]?" | Synthesis across sentences | Semantic window vs. structural |
| Q8 | "What does the document recommend for [use case or scenario]?" | Recommendation retrieval | Structural (recommendation often closes a section) |
| Q9 | "Summarize the relationship between [entity A] and [entity B] as described across the document." | Cross-section synthesis | All three — tests if a single chunk contains enough signal |
| Q10 | "What evidence or example is given to support the claim that [key argument]?" | Evidence retrieval | Fixed-size may separate claim from evidence; structural may keep them together |

For each query, before running retrieval, **manually identify the gold chunk** — the passage in the source text that a human would cite as the best answer. Record its `char_start/char_end`. This becomes the ground truth for evaluation (Phase 6).

---

## Phase 6 — Evaluation Method

### 6.1 Primary Metric: Hit-Rate@3 with Cosine Similarity Score

**Primary metric: Hit-Rate@3 (HR@3)**

Definition: For a given query and strategy, HR@3 = 1 if the gold chunk (or a chunk with ≥ 50% character overlap with the gold chunk) appears in the top-3 retrieved results; 0 otherwise.

**Why HR@3, not cosine similarity score alone?**
- Raw cosine similarity scores are not comparable across strategies — a semantic chunk that is twice as long as a fixed chunk will have a different score distribution.
- HR@3 is binary and interpretable: either the right passage was retrieved or it wasn't.
- Top-3 (not top-1) because in real RAG systems, the LLM sees multiple retrieved passages; retrieving the right one in 3rd place is still useful.
- No pre-existing labeled dataset exists, but HR@3 requires only a **single manually-identified gold chunk per query** (10 total identifications), which is feasible.

ASSUMPTION: "Gold chunk" is identified by reading the document and finding the passage that most directly answers the query. This is done **before** running queries to prevent confirmation bias.

**Secondary metric (recorded but not primary): Mean Reciprocal Rank (MRR@5)**
- MRR@5 = 1/rank of first relevant result, averaged over all 10 queries.
- Recorded to show whether the gold chunk is ranked 1st vs. 3rd.

**Tertiary metric (recorded for qualitative analysis): Top-1 Cosine Similarity Score**
- The cosine similarity of the top-ranked result. Useful for spotting strategy-level score distribution differences.

---

### 6.2 Query Execution Procedure

For each of the 10 queries and each of the 3 strategies:

1. Embed the query text using the same model (`text-embedding-3-small`).
2. Execute the following SQL (parameterized):

```sql
SELECT
    chunk_id,
    strategy,
    source_page,
    chunk_text,
    1 - (embedding <=> $1::vector) AS cosine_similarity
FROM document_chunks
WHERE strategy = $2
ORDER BY embedding <=> $1::vector
LIMIT 5;
```

3. Record the full top-5 result list: `(chunk_id, strategy, source_page, cosine_similarity, chunk_text_preview)`.
4. For each result, compute character overlap with the pre-identified gold chunk span:
   - `overlap = max(0, min(chunk_end, gold_end) - max(chunk_start, gold_start))`
   - A result is "relevant" if `overlap / (gold_end - gold_start) >= 0.5`.
5. Determine rank of first relevant result → compute MRR@5.
6. HR@3 = 1 if any result in rank 1–3 is relevant.

This gives a **3×10 matrix** of (strategy × query) with HR@3, MRR@5, and top-1 cosine score for each cell.

---

### 6.3 Producing the Markdown Comparison Table

Aggregate the 3×10 matrix into the following table structure.

**Table 1: Per-Query Results**

| Query | Description | Gold Page | Fixed HR@3 | Struct HR@3 | Semantic HR@3 | Fixed Top-1 Score | Struct Top-1 Score | Semantic Top-1 Score |
|---|---|---|---|---|---|---|---|---|
| Q1 | Definition of [X] | p.N | 1 | 1 | 0 | 0.87 | 0.91 | 0.79 | ... |
| ... | | | | | | | | |
| **AVG** | | | | | | | | |

**Table 2: Strategy Summary**

| Strategy | Avg HR@3 | Avg MRR@5 | Avg Top-1 Cosine | Chunk Count | Avg Token Count | Best Query Types |
|---|---|---|---|---|---|---|
| Fixed (512t, 64t overlap) | X/10 | X.XX | X.XX | ~45 | ~512 | Q5, Q1 |
| Structural (400t target) | X/10 | X.XX | X.XX | ~40 | ~350 | Q2, Q4, Q8 |
| Semantic (5-sentence, stride 2) | X/10 | X.XX | X.XX | ~1200 | ~120 | Q6, Q7 |

**Table 3: Qualitative Observations**

| Query | Observation |
|---|---|
| Q1 | Fixed-size split the definition across chunks; structural captured the full paragraph. |
| Q3 | Semantic window retrieved a chunk with one side of the contrast but not both. |
| ... | ... |

All three tables are written to `results/retrieval_comparison.md` at the end of the evaluation run.

---

## Phase 7 — Checklist: Success Criteria Mapping

### SC1: Supabase pgvector configured with HNSW or IVFFlat index

| Item | Phase | Status |
|---|---|---|
| `CREATE EXTENSION vector` executed | Phase 1.1 | ✓ Defined |
| `document_chunks` table with `VECTOR(1536)` column | Phase 1.1 | ✓ Defined |
| HNSW index created with `m=16, ef_construction=64` | Phase 1.2 | ✓ Defined |
| Index choice justified (HNSW over IVFFlat for < 1k vectors) | Phase 1.2 | ✓ Justified |

### SC2: 3 chunking strategies implemented and compared

| Item | Phase | Status |
|---|---|---|
| Fixed-size (512t / 64t overlap) fully specified | Phase 3A | ✓ Defined |
| Structural/recursive (paragraph → sentence fallback, 400t target) | Phase 3B | ✓ Defined |
| Semantic sliding sentence-window (5 sentences, stride 2) | Phase 3C | ✓ Defined |
| All strategies produce `chunk_id`, `strategy`, `source_page`, `char_start/end` | Phase 4.3 | ✓ Defined |

### SC3: 10 semantic queries with documented results

| Item | Phase | Status |
|---|---|---|
| 10 query types defined with rationale | Phase 5 | ✓ Defined |
| Queries designed to differentiate strategies (not generic) | Phase 5 | ✓ Defined |
| Gold chunk identification procedure defined | Phase 5 | ✓ Defined |
| Execution procedure (SQL, cosine similarity, top-5) | Phase 6.2 | ✓ Defined |
| Per-query result table structure | Phase 6.3, Table 1 | ✓ Defined |

### SC4: Markdown comparison table of retrieval quality

| Item | Phase | Status |
|---|---|---|
| "Retrieval quality" defined as HR@3 (primary), MRR@5, cosine score (secondary) | Phase 6.1 | ✓ Defined |
| Metric justified given no pre-existing ground truth | Phase 6.1 | ✓ Justified |
| Per-query results table (Table 1) | Phase 6.3 | ✓ Defined |
| Strategy summary table (Table 2) | Phase 6.3 | ✓ Defined |
| Qualitative observations table (Table 3) | Phase 6.3 | ✓ Defined |
| Output path: `results/retrieval_comparison.md` | Phase 6.3 | ✓ Defined |

---

## Consolidated Assumption Log

| # | Assumption | Risk if Wrong | Mitigation |
|---|---|---|---|
| A1 | pgvector ≥ 0.5.0 installed in Supabase | HNSW not available | Check version; fall back to IVFFlat with `lists=16` |
| A2 | PDF is text-based, not scanned | `pdfplumber` returns empty text | Add `pytesseract` + `pdf2image` OCR preprocessing |
| A3 | OpenAI API key available as `OPENAI_API_KEY` | Embeddings cannot be generated | Switch to `sentence-transformers/all-MiniLM-L6-v2` (dim=384, requires schema change) |
| A4 | Document ≤ 100k tokens total | Single-pass tokenization runs out of memory | Stream token list in pages |
| A5 | PDF is single-column, non-creative, English | Layout extraction and NLP sentence splitting fail | Use `pymupdf` for multi-column; retrain spaCy or use NLTK Punkt for other languages |
| A6 | spaCy `en_core_web_sm` handles sentence segmentation correctly | Bullet lists, equations misidentified as sentence ends | Post-process: merge lines ending without terminal punctuation |
| A7 | 5-sentence window ≤ 512 tokens | Embedding call fails | Detect and reduce window to 3 sentences; log occurrences |
| A8 | Gold chunks can be identified by one human reviewer before querying | No ground truth → metric undefined | Use 2 reviewers + Cohen's kappa if document is ambiguous |

---

*End of implementation plan. Every section maps directly to at least one success criterion. A developer should be able to execute each phase sequentially without additional design decisions.*
