[🗺 Course Roadmap](../../ROADMAP.html) · [← 16 Streaming & HITL](../16_streaming_and_hitl/README.md) · [18 Multi-Agent →](../18_multi_agent/README.md)

# Module 17 — Advanced RAG

## Objective

Act 3 of the TechCorp story opens with a complaint queue: "the assistant can't find the answer when I don't phrase it exactly like the handbook." Module 09 already quantified that pain — with hash embeddings, paraphrase questions retrieve the right document only **60%** of the time versus **88%** overall. Leadership doesn't want a promise that "advanced RAG" fixes it; they want a table. In this module you upgrade the retrieval pipeline one technique at a time — hybrid search, reranking, query rewriting — and **re-run the Module 09 evaluation after each** so every claim of improvement is backed by a measured number. Crucially, you also learn to report honestly when a technique *doesn't* help on this corpus. That is a real finding, not a failure.

## Difficulty

Advanced

## Prerequisites

- Module 08 completed (you have a working `RAGPipeline`: retrieve → augment → generate → cite)
- Module 09 completed (you built the deterministic evaluation harness and read `artifacts/evaluation_report.md`)
- You understand hit@k, chunks, embeddings, and the `SOURCES:` / abstention contract
- No API key required — everything runs offline against hash embeddings and the mock LLM. The optional headline run uses local sentence-transformers (free, downloads once).

## What you will build

Three retrieval primitives in `starter/advanced_rag_lab.py`, then the experiment that measures them:

1. `min_max_normalize` + `hybrid_fuse` — fuse BM25 keyword scores with vector similarity onto a common scale
2. `overlap_rerank` — a deterministic, offline token-overlap reranker (the honest stand-in for a cross-encoder)
3. `parse_rewrites` — turn a query-rewriting LLM reply into a deduped multi-query list

You then run `solution/run_experiment.py`, which chains these through the shared `AdvancedRAGPipeline` under five configurations (baseline / +hybrid / +rerank / +rewrite / all), scores each against the evaluation dataset, and writes the comparison report.

The heavy plumbing — Chroma-backed vector search, the BM25 index, the `CrossEncoderReranker`, the configurable `AdvancedRAGPipeline` — already lives in the shared library `src/techcorp_agent/rag/advanced.py`. You read and reuse it; the lab is about the retrieval *logic* and the *measurement*, not re-plumbing.

## Files involved

```text
course/17_advanced_rag/
├── README.md            ← you are here
├── concepts.md          ← read first: naive-RAG failure modes, hybrid, rerank, multi-query, and when naive is enough
├── lab.md               ← the tasks (baseline → hybrid → rerank → rewrite → table → conclusions)
├── starter/
│   └── advanced_rag_lab.py   ← your working file (has TODO markers)
├── solution/
│   ├── advanced_rag_lab.py   ← reference primitives + experiment harness
│   └── run_experiment.py     ← runs all five configs, writes the artifact
├── tests/
│   ├── test_solution.py ← proves the reference works (always runs)
│   └── test_my_work.py  ← your completion gate (skips until TODOs are gone)
└── checklist.md         ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/rag/advanced.py` (the retrieval upgrades), `src/techcorp_agent/rag/pipeline.py` (the pipeline you extend), `src/techcorp_agent/evaluation/` (`metrics.py`, `runner.py`), `data/evaluation/eval_dataset.json`, `artifacts/evaluation_report.md` (the Module 09 baseline)

## Commands

```bash
# From the repository root.

# See the reference experiment run offline (fast, reproducible) and write the report:
TECHCORP_OFFLINE=true uv run python course/17_advanced_rag/solution/run_experiment.py

# Include the real sentence-transformers headline (downloads models once, free):
uv run python course/17_advanced_rag/solution/run_experiment.py

# Read the report it wrote:
#   artifacts/retrieval_improvement_report.md

# Work the lab:
#   edit course/17_advanced_rag/starter/advanced_rag_lab.py

# Test (offline by default; your tests skip until the TODOs are gone):
uv run pytest course/17_advanced_rag -q

# Confirm the shared advanced-RAG library still passes too:
uv run pytest course/17_advanced_rag tests/test_advanced_rag.py -q
```

## Deliverable

`artifacts/retrieval_improvement_report.md`: a per-configuration table (hit@4, latency, added complexity), a per-category breakdown, "when is each technique worth it" guidance, and honest findings — including the negative results — for both the offline and the sentence-transformers runs.
