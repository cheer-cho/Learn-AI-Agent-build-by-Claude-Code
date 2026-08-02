[🗺 Course Roadmap](../../ROADMAP.html) · [← 06 Semantic Search](../06_semantic_search/README.md) · [08 RAG →](../08_rag/README.md)

# Module 07 — Vector Databases and Chunking

## Objective

Graduate TechCorp's search from Module 06's in-memory list to a real vector database. You will persist embeddings in ChromaDB, learn every knob on the document chunker, and then answer the question every RAG team argues about — *what chunk size is best?* — the only defensible way: by running an experiment against the evaluation dataset and writing up the results.

## Difficulty

Intermediate

## Prerequisites

- Module 05 completed (you know what an embedding is, and why hash embeddings are a word-overlap stand-in, not semantics)
- Module 06 completed (you have ranked chunks by cosine similarity and seen top-k retrieval work — and recomputed every embedding on every run)
- No API key required — embeddings run locally. The first sentence-transformers use downloads the model once (~90 MB); set `TECHCORP_OFFLINE=true` to skip the download and use hash embeddings instead (clearly labeled in all output).

## What you will build

**Lab A — the chunking experiment** (`starter/chunking_experiment.py`): a script that, for at least three chunking configurations (small fixed / medium fixed / paragraph-aware):

1. Chunks the whole TechCorp corpus and indexes it into a *throwaway* ChromaDB collection
2. Runs the 15 answerable + paraphrase questions from `data/evaluation/eval_dataset.json`
3. Measures the retrieval hit-rate (expected source doc in the top-4 results), chunk count, average chunk length, and duplicate-content rate
4. Writes a comparison report to `artifacts/chunking_report.md`, including the failure cases and which embedding client produced the numbers

**Lab B — the ChromaDB tour** (`chroma_tour.py`, a scratch file you create): create a persistent collection, add chunks with source metadata, query semantically, filter by category, delete and rebuild the collection safely, and prove persistence across a process restart.

## Files involved

```text
course/07_vector_database/
├── README.md                     ← you are here
├── concepts.md                   ← read first: vector stores, ChromaDB, chunking knobs
├── lab.md                        ← the tasks (Lab A and Lab B)
├── starter/
│   └── chunking_experiment.py    ← your working file (has TODO markers)
├── solution/
│   ├── chunking_experiment.py    ← reference implementation
│   └── run_experiment.py         ← main entry; writes artifacts/chunking_report.md
├── tests/
│   ├── test_solution.py          ← proves the reference works (always runs)
│   └── test_my_work.py           ← your completion gate (skips until TODOs are gone)
└── checklist.md                  ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/vectorstore/chroma_store.py`, `src/techcorp_agent/documents/chunking.py`, `src/techcorp_agent/documents/loader.py`, `src/techcorp_agent/embeddings/`

## Commands

```bash
# From the repository root.

# Setup (once, if you haven't):
uv sync

# See the reference experiment run and write the report:
uv run python course/07_vector_database/solution/run_experiment.py
# ... then read artifacts/chunking_report.md

# Work the lab:
uv run python course/07_vector_database/starter/chunking_experiment.py

# Test (offline, temp dirs only; your tests skip until the TODOs are gone):
uv run pytest course/07_vector_database -q

# No-download mode (hash embeddings; numbers measure word overlap, not semantics):
TECHCORP_OFFLINE=true uv run python course/07_vector_database/solution/run_experiment.py

# Build the shared course index the later modules will query (paragraph config):
uv run python scripts/build_index.py
```
