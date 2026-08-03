# Module 07 — Chunking Experiment Report

- **Embedding client:** `hash-embedding-384d` (offline hash client (word-overlap only))
- **Questions:** 15 (answerable + paraphrase, from `data/evaluation/eval_dataset.json`)
- **Hit criterion:** an expected source document appears among the top-4 retrieved chunks
- **Duplicate-content rate:** fraction of 8-word shingles appearing in more than one chunk

> **Embedding-client caveat:** hash-embedding numbers measure *word overlap*, not semantics. Only sentence-transformers results reflect real semantic retrieval quality; hash results are a plumbing check, not an evaluation.

## Comparison

| Config | Strategy | Chunk size | Overlap | Chunks | Avg chunk chars | Hit-rate | Duplicate rate |
|---|---|---:|---:|---:|---:|---:|---:|
| small-fixed | fixed | 300 | 30 | 155 | 283 | 87% | 0.1% |
| medium-fixed | fixed | 800 | 100 | 63 | 709 | 87% | 12.0% |
| paragraph | paragraph | 1200 | 0 | 41 | 966 | 87% | 0.0% |

## Observed failure cases

### small-fixed — 2 missed

- **eval-013** — "Can I sync my work files to my own Dropbox account?" (expected `hr-equipment`; retrieved docs: `privacy-gdpr, privacy-retention, hr-international-remote, support-refund-damaged`)
- **eval-014** — "During which hours does everyone need to be reachable for teamwork, regardless of where they work?" (expected `hr-remote-work`; retrieved docs: `hr-vacation, hr-equipment, hr-international-remote`)

### medium-fixed — 2 missed

- **eval-012** — "Where can I find the staff time-off guidelines, and what's the headline entitlement?" (expected `hr-vacation`; retrieved docs: `support-refund-damaged, hr-international-remote, support-escalation, privacy-regional`)
- **eval-013** — "Can I sync my work files to my own Dropbox account?" (expected `hr-equipment`; retrieved docs: `privacy-retention, hr-international-remote, privacy-regional, privacy-gdpr`)

### paragraph — 2 missed

- **eval-012** — "Where can I find the staff time-off guidelines, and what's the headline entitlement?" (expected `hr-vacation`; retrieved docs: `privacy-deletion, support-escalation, privacy-gdpr`)
- **eval-013** — "Can I sync my work files to my own Dropbox account?" (expected `hr-equipment`; retrieved docs: `privacy-retention, hr-international-remote, privacy-gdpr`)

