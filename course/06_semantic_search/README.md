[🗺 Course Roadmap](../../ROADMAP.html) · [← 05 Embeddings](../05_embeddings/README.md) · [07 Vector Databases →](../07_vector_database/README.md)

# Module 06 — Semantic Search

## Objective

Turn Module 05's embeddings into a working search engine: index the entire TechCorp policy corpus in memory, ask it real questions ("Can I wear jeans at the office?"), and get back ranked chunks with similarity scores — then run the same questions through plain keyword search and see exactly where each approach wins and fails. Every stage of the pipeline is code you can read; no vector database, no black boxes. That arrives in Module 07, once you know precisely what it will be doing for you.

## Difficulty

Intermediate

## Prerequisites

- Module 05 completed (you know what an embedding is and have compared vectors with cosine similarity)
- `uv sync` works and `.env` exists (from Module 00)
- No API key required — embeddings run locally. The sentence-transformers model (~90 MB) downloads once on first use; without it, everything falls back to the offline hash client (with honestly degraded results — the lab explains exactly how degraded).

## What you will build

A `SearchEngine` class in `search_engine.py` that:

1. Loads all 13 TechCorp policy documents with `load_documents(data_dir)` (the security lab corpus stays excluded)
2. Splits them into chunks with `chunk_document` and embeds every chunk in one batch
3. Stores chunks and vectors in two plain in-memory lists — the whole "index"
4. Embeds an incoming query and ranks every chunk by cosine similarity
5. Returns the top-k results as `RetrievedChunk` objects: document title, chunk text, score
6. Applies an optional `min_score` threshold so near-misses can be dropped
7. Implements `keyword_search` (word-overlap scoring) as the baseline to beat
8. Runs four evaluation queries and prints semantic vs keyword results side by side

## Files involved

```text
course/06_semantic_search/
├── README.md               ← you are here
├── concepts.md             ← read first: the pipeline, top-k, thresholds, precision/recall
├── lab.md                  ← the tasks
├── starter/
│   └── search_engine.py    ← your working file (has TODO markers)
├── solution/
│   └── search_engine.py    ← reference implementation (runs offline if it must)
├── tests/
│   ├── test_solution.py    ← proves the reference works (always runs, offline)
│   └── test_my_work.py     ← your completion gate (skips until TODOs are gone)
└── checklist.md            ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/documents/loader.py`, `src/techcorp_agent/documents/chunking.py`, `src/techcorp_agent/embeddings/`, `src/techcorp_agent/similarity.py`, `src/techcorp_agent/schemas.py`

## Commands

```bash
# From the repository root.

# See the reference implementation run (downloads the embedding model on first use):
uv run python course/06_semantic_search/solution/search_engine.py

# Work the lab:
uv run python course/06_semantic_search/starter/search_engine.py

# Test (offline, deterministic; your tests skip until the TODOs are gone):
uv run pytest course/06_semantic_search -q

# Force offline hash embeddings (to see honestly how much semantics you lose):
TECHCORP_OFFLINE=true uv run python course/06_semantic_search/solution/search_engine.py
```
