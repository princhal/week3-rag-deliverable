# Kiro Skills Inventory
### RAG System Project — Week 3 Deliverable

---

## Installed Skills

| Skill | Domain | Location | Purpose |
|---|---|---|---|
| **rag-architect** | Data | `~/.kiro/skills/rag-architect/` | RAG pipeline design, chunking strategy selection, retrieval quality evaluation (precision@k, recall@k, NDCG) |
| **embedding-strategies** | AI/ML | `~/.kiro/skills/embedding-strategies/` | Embedding model selection and optimization for semantic search and RAG applications |
| **senior-prompt-engineer** | AI/ML | `~/.kiro/skills/senior-prompt-engineer/` | Prompt optimization, RAG metrics (relevance, faithfulness, coverage), eval-driven iteration |
| **async-python-patterns** | AI/ML | `~/.kiro/skills/async-python-patterns/` | Python asyncio, concurrent programming, async/await for high-performance API calls |
| **hugging-face-trackio** | Debugging | `~/.kiro/skills/hugging-face-trackio/` | ML experiment tracking, metrics logging, alerts, and visualization |

---

## Skill-to-Phase Mapping

| Plan Phase | Relevant Skill(s) |
|---|---|
| Phase 1 — Schema & Index | — (SQL files self-contained) |
| Phase 2 — PDF Ingestion & Cleaning | — (pdfplumber, custom pipeline) |
| Phase 3 — Chunking Strategies | **rag-architect**, **embedding-strategies** |
| Phase 4 — Embeddings | **embedding-strategies**, **async-python-patterns** |
| Phase 5 — Query Design | **rag-architect**, **senior-prompt-engineer** |
| Phase 6 — Evaluation | **rag-architect**, **senior-prompt-engineer**, **hugging-face-trackio** |

---

## MCP Server

| Server | Command | Config Location |
|---|---|---|
| **skills-mcp** v2.116.0 | `/opt/homebrew/bin/skills-mcp` | `~/.kiro/settings/mcp.json` |

Catalog: **9,238 skills** · 11 repos · 20 domains

---

## How to Use Skills in Kiro

Reference a skill in chat using `#` followed by the skill name:
- `#rag-architect` — activate RAG design guidance
- `#embedding-strategies` — activate embedding optimization guidance
- `#senior-prompt-engineer` — activate prompt and eval guidance
- `#async-python-patterns` — activate async Python guidance
- `#hugging-face-trackio` — activate experiment tracking guidance

---

## Sources

- [skills-mcp GitHub](https://github.com/gengirish/skills-mcp)
- [Skills catalog browser](https://skillsmcp.intelliforge.tech)
- Installed via `mcp_skills_install_skill` tool on 2026-08-30
