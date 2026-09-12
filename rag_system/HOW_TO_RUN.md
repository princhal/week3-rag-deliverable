# How to Run the RAG Pipeline
### Minimal steps — execute in order

---

## Prerequisites (one-time)

- Python 3.11.9 via pyenv ✅ already installed
- All dependencies ✅ already installed
- Model `all-MiniLM-L6-v2` ✅ already downloaded
- PDF ✅ already at `data/source.pdf`

---

## Step 1 — Reset Supabase (one-time)

1. Open: https://supabase.com/dashboard/project/mcipzicqpxmgujxyhjrr/sql/new
2. Paste the entire contents of `sql/006_reset_384.sql`
3. Click **Run**
4. You should see: `Success. No rows returned`

---

## Step 2 — Run the pipeline

Open **Terminal.app** and run these commands one by one:

```zsh
cd /Users/princhal/Desktop/Week3/Deliverable/rag_system
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
./run.sh
```

The pipeline runs 6 stages automatically:

| Stage | What it does | Time |
|---|---|---|
| 1. extract | Reads PDF, extracts text | ~5s |
| 2. clean | Removes headers, normalises text | ~2s |
| 3. chunk | Splits into 200 chunks (3 strategies) | ~10s |
| 4. embed | Generates embeddings locally, uploads to Supabase | ~30s |
| 5. query | Runs 10 semantic queries | ~20s |
| 6. evaluate | Scores results, writes comparison table | ~2s |

Total: ~70 seconds

---

## Step 3 — View results

After the pipeline completes, open:

```
results/retrieval_comparison.md
```

This contains the full comparison table of all 3 chunking strategies across 10 queries.

---

## Re-running a single stage

```zsh
./run.sh --stage embed        # re-run embed only
./run.sh --from-stage query   # re-run query + evaluate
./run.sh --stage evaluate     # re-run evaluation only
```

---

## Troubleshooting

| Error | Fix |
|---|---|
| `source.pdf not found` | Make sure PDF is at `data/source.pdf` |
| `DB ERROR` on embed | Re-run `sql/006_reset_384.sql` in Supabase |
| `queries.json not found` | File is at `data/queries.json` — already filled in |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |

---

## Project structure

```
rag_system/
├── run.sh                  ← entry point
├── main.py                 ← pipeline runner
├── data/
│   ├── source.pdf          ← your PDF
│   └── queries.json        ← 10 pre-filled queries
├── src/
│   ├── extract.py          ← Stage 1
│   ├── clean.py            ← Stage 2
│   ├── chunk.py            ← Stage 3
│   ├── embed.py            ← Stage 4 (local embeddings)
│   ├── query.py            ← Stage 5
│   └── evaluate.py         ← Stage 6
├── sql/
│   └── 006_reset_384.sql   ← run in Supabase first
└── results/
    └── retrieval_comparison.md  ← output
```
