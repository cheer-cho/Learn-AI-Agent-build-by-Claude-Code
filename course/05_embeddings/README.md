[🗺 Course Roadmap](../../ROADMAP.html) · [← 04 Prompt Engineering](../04_prompt_engineering/README.md) · [06 Semantic Search →](../06_semantic_search/README.md)

# Module 05 — Embeddings

## Objective

Understand how text becomes **geometry**: embeddings turn phrases into vectors so that *meaning*, not wording, determines how close two texts are. You will embed TechCorp-style phrases, measure their cosine similarity, rank documents against a query by meaning, and catch a naive keyword matcher making both of its classic mistakes — a false positive and a false negative — that semantic similarity avoids.

This module opens Level 2 of the course. Module 01 proved you can't paste everything into the context window; retrieval is the answer, and embeddings are the machinery every retrieval system (Modules 06–08) is built on.

## Difficulty

Intermediate

## Prerequisites

- Modules 00–04 completed (environment green; you know what tokens and context windows are from Module 01).
- **No API key required.** Embeddings run locally via `sentence-transformers` — free, with a one-time ~90 MB model download on first use. Everything degrades gracefully to a deterministic offline stand-in if the download isn't possible, and all tests run fully offline.

## What you will build

An **embeddings lab** (`embeddings_lab.py`) that:

1. Loads an embedding client (real semantic model, with a safe offline fallback).
2. Embeds a batch of phrases and inspects the vectors' shape and dimension.
3. Computes cosine similarity between chosen phrase pairs — showing that "Employee vacation policy" and "Staff time-off guidelines" are *close* despite sharing almost no words.
4. Ranks five TechCorp documents against a help-desk query using `rank_by_similarity`.
5. Compares that semantic ranking against a naive keyword-overlap ranking and identifies one false positive and one false negative of keyword matching.
6. (Optional) Projects the vectors to 2D for a visual — only if `matplotlib` and `scikit-learn` happen to be installed.

## Files involved

```text
course/05_embeddings/
├── README.md                   ← you are here
├── concepts.md                 ← read this first
├── lab.md                      ← then follow the tasks here
├── starter/embeddings_lab.py   ← your working file (has TODO markers)
├── solution/embeddings_lab.py  ← reference implementation (peek only when stuck)
├── tests/test_solution.py      ← always runs; verifies the reference solution
├── tests/test_my_work.py       ← verifies YOUR starter once the TODOs are gone
└── checklist.md                ← self-check before moving on
```

Shared code you will import (already built for you):

- `src/techcorp_agent/embeddings/base.py` — the `EmbeddingClient` protocol
- `src/techcorp_agent/embeddings/st_client.py` — `SentenceTransformerClient` (real semantics, local, free)
- `src/techcorp_agent/embeddings/hash_client.py` — `HashEmbeddingClient` (deterministic offline stand-in, used by tests)
- `src/techcorp_agent/embeddings/factory.py` — `get_embedding_client()`
- `src/techcorp_agent/similarity.py` — `cosine_similarity()`, `rank_by_similarity()`

## Commands

Run everything from the repository root.

```bash
# 1. Read the concepts, then see the finished behavior (first run downloads
#    the ~90 MB model once; later runs are instant):
uv run python course/05_embeddings/solution/embeddings_lab.py

# 2. Do the lab in the starter (see lab.md for the tasks):
uv run python course/05_embeddings/starter/embeddings_lab.py

# 3. Check your work (auto-skips until you remove the TODO markers):
uv run pytest course/05_embeddings/tests/test_my_work.py -q

# 4. Run the whole module's test suite (fully offline — no download needed):
uv run pytest course/05_embeddings -q
```

When all tests in step 3 pass, open [checklist.md](checklist.md).
