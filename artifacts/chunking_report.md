# Module 07 — Chunking Experiment Report

- **Embedding client:** `sentence-transformers/all-MiniLM-L6-v2` (sentence-transformers)
- **Questions:** 15 (answerable + paraphrase, from `data/evaluation/eval_dataset.json`)
- **Hit criterion:** an expected source document appears among the top-4 retrieved chunks
- **Duplicate-content rate:** fraction of 8-word shingles appearing in more than one chunk

> **Embedding-client caveat:** hash-embedding numbers measure *word overlap*, not semantics. Only sentence-transformers results reflect real semantic retrieval quality; hash results are a plumbing check, not an evaluation.

## Comparison

| Config | Strategy | Chunk size | Overlap | Chunks | Avg chunk chars | Hit-rate | Duplicate rate |
|---|---|---:|---:|---:|---:|---:|---:|
| small-fixed | fixed | 300 | 30 | 155 | 283 | 100% | 0.1% |
| medium-fixed | fixed | 800 | 100 | 63 | 709 | 100% | 12.0% |
| paragraph | paragraph | 1200 | 0 | 41 | 966 | 100% | 0.0% |

## Observed failure cases

### small-fixed — 0 missed

No misses: every question found its expected source in the top results.

### medium-fixed — 0 missed

No misses: every question found its expected source in the top results.

### paragraph — 0 missed

No misses: every question found its expected source in the top results.

