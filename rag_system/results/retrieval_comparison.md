# RAG Retrieval Quality Comparison

_Generated: 2026-09-12 21:44_

**Metrics:**
- **HR@3** (primary): 1 if gold chunk in top-3 results, else 0
- **MRR@5** (secondary): 1/rank of first relevant result in top-5
- **Top-1 Cosine**: cosine similarity of rank-1 result
- Relevance threshold: ≥50% character overlap with gold chunk

---

## Table 1: Per-Query Results

| Query | Type | Gold Page | Fixed HR@3 | Struct HR@3 | Sem HR@3 | Fixed Top-1 | Struct Top-1 | Sem Top-1 |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Q1** | single-fact / definition | 3 | 0 | 1 | 0 | 0.4747 | 0.6185 | 0.6967 |
| **Q10** | evidence retrieval | 3 | 1 | 0 | 1 | 0.3667 | 0.3389 | 0.4896 |
| **Q2** | multi-part fact | 3 | 0 | 1 | 0 | 0.4761 | 0.5728 | 0.6209 |
| **Q3** | contrastive | 5 | 0 | 0 | 0 | 0.5771 | 0.5736 | 0.6434 |
| **Q4** | context-dependent | 3 | 0 | 1 | 0 | 0.4912 | 0.4198 | 0.4789 |
| **Q5** | single precise fact | 3 | 1 | 0 | 0 | 0.4508 | 0.5798 | 0.5864 |
| **Q6** | sequential / procedural | 7 | 0 | 0 | 0 | 0.4088 | 0.3538 | 0.7006 |
| **Q7** | synthesis across sentence | 5 | 0 | 0 | 0 | 0.6679 | 0.6839 | 0.7026 |
| **Q8** | recommendation retrieval | 8 | 0 | 0 | 0 | 0.3893 | 0.4110 | 0.4736 |
| **Q9** | cross-section synthesis | 10 | 0 | 0 | 0 | 0.6118 | 0.5242 | 0.6688 |
| **AVG** | | | **0.20** | **0.30** | **0.10** | **0.49** | **0.51** | **0.61** |

## Table 2: Strategy Summary

| Strategy | Avg HR@3 | Avg MRR@5 | Avg Top-1 Cosine | Best Query Types |
|---|:---:|:---:|:---:|---|
| Fixed-size (512t, 64t overlap) | 0.20 | 0.220 | 0.4914 | Q1, Q5 (precise single-fact lookups) |
| Structural (400t target, para→sent fallback) | 0.30 | 0.300 | 0.5076 | Q2, Q4, Q8 (paragraph/section-level) |
| Semantic (5-sentence window, stride 2) | 0.10 | 0.100 | 0.6061 | Q6, Q7 (sequential and multi-sentence) |

## Table 3: Qualitative Observations

> Fill in this table after reviewing the raw results in `results/raw_results.json`.

| Query | Winner | Observation |
|---|---|---|
| **Q1** | Structural | _[Manual observation to be filled in]_ |
| **Q10** | Semantic | _[Manual observation to be filled in]_ |
| **Q2** | Structural | _[Manual observation to be filled in]_ |
| **Q3** | Semantic | _[Manual observation to be filled in]_ |
| **Q4** | Structural | _[Manual observation to be filled in]_ |
| **Q5** | Fixed | _[Manual observation to be filled in]_ |
| **Q6** | Structural | _[Manual observation to be filled in]_ |
| **Q7** | Semantic | _[Manual observation to be filled in]_ |
| **Q8** | Semantic | _[Manual observation to be filled in]_ |
| **Q9** | Semantic | _[Manual observation to be filled in]_ |

## Appendix: Chunk Counts

| Strategy | Chunk Count | Avg Tokens |
|---|:---:|:---:|
| Fixed-size (512t, 64t overlap) | _(from DB)_ | ~512 |
| Structural (400t target) | _(from DB)_ | ~350 |
| Semantic (5-sentence, stride 2) | _(from DB)_ | ~80–120 |

_Run `sql/002_verify.sql` to get exact counts from the database._
