# TechCorp Retrieval Improvement Report

Module 17 re-runs the Module 09 retrieval evaluation under five
configurations to measure — not assume — what each advanced-RAG
technique does on the TechCorp corpus. Scored categories:
`answerable, paraphrase, multi_chunk` (the categories where retrieval is
under test; unanswerable/ambiguous expect no sources, so hit@k is
vacuously 1.0 there and they are excluded).

**The rule for reading this report:** every number is measured against
`data/evaluation/eval_dataset.json`. Where a technique did not help,
the table says so. A flat or negative delta is a real finding.

## Run context

- **headline embeddings**: sentence-transformers
- **offline embeddings**: hash-embedding-384d
- **live embeddings**: sentence-transformers/all-MiniLM-L6-v2
- **reranker (offline)**: OverlapReranker (token-overlap approximation)
- **reranker (live)**: cross-encoder/ms-marco-MiniLM-L-6-v2
- **k (retrieval depth scored)**: 4
- **documents indexed**: 13
- **examples scored**: 18

## Headline: sentence-transformers (real semantic embeddings)

| config | complexity added | hit@4 | Δ vs baseline | latency ms/query |
|---|---|---:|---:|---:|
| `baseline` | none (Module 08 vector top-k) | 100% | ±0 | 8.2 |
| `+hybrid` | BM25 index + score fusion | 100% | ±0 | 4.4 |
| `+rerank` | hybrid + reranker pass | 100% | ±0 | 28.5 |
| `+rewrite` | hybrid + multi-query rewriting | 89% | -11% | 13.8 |
| `all` | hybrid + rewrite + rerank | 100% | ±0 | 35.9 |

### Per-category hit@4 (headline run)

| config | answerable | multi_chunk | paraphrase |
|---|---:|---:|---:|
| `baseline` | 100% | 100% | 100% |
| `+hybrid` | 100% | 100% | 100% |
| `+rerank` | 100% | 100% | 100% |
| `+rewrite` | 100% | 33% | 100% |
| `all` | 100% | 100% | 100% |

## Offline reference: hash embeddings

The same experiment with the deterministic hash embeddings the test
suite uses. Hash embeddings match on word overlap only (no
semantics), so absolute numbers differ from the headline — but this
is the run every learner can reproduce with `TECHCORP_OFFLINE=true`.

| config | hit@4 | Δ vs baseline | latency ms/query |
|---|---:|---:|---:|
| `baseline` | 83% | ±0 | 0.6 |
| `+hybrid` | 94% | +11% | 0.9 |
| `+rerank` | 100% | +17% | 1.0 |
| `+rewrite` | 78% | -6% | 2.2 |
| `all` | 89% | +6% | 2.3 |

## When is each technique worth it?

- **Hybrid search (BM25 + vectors).** Worth it whenever queries carry
  exact tokens the corpus also uses verbatim — product codes, policy
  names, error strings. BM25 and dense embeddings fail *differently*:
  BM25 is blind to synonyms, vectors dilute rare keywords. Fusing them
  recovers the union. Cheap (an in-memory index), so it is usually the
  first upgrade to reach for.
- **Reranking (cross-encoder).** Worth it when retrieval returns the
  right chunk but not in the top-k the generator sees — a precision fix,
  not a recall fix. It cannot rescue a chunk retrieval never fetched.
  Adds real latency (a transformer pass over the shortlist) and, live, a
  model download, so adopt it only after measuring that ordering — not
  coverage — is the bottleneck.
- **Query rewriting / multi-query.** Worth it for paraphrase-heavy or
  vague questions, where one alternate phrasing shares the corpus's
  words. Cost is linear in the number of rewrites (N× the retrievals,
  plus one LLM call to generate them), so it is the most expensive stage
  per query.

## Honest findings on THIS corpus

On the **offline hash-embedding** run (baseline hit@4 83%):

  - `+hybrid`: HELPED (+11%). Paraphrase category: 60% → 80%.
  - `+rerank`: HELPED (+17%). Paraphrase category: 60% → 100%.
  - `+rewrite`: HURT (-6%) — a real negative result. Paraphrase category: 60% → 40%.
  - `all`: HELPED (+6%). Paraphrase category: 60% → 80%.

On the **live sentence-transformer** run (baseline hit@4 100%):

  - `+hybrid`: NO CHANGE — did not move the needle on this corpus. Paraphrase category unchanged at 100%.
  - `+rerank`: NO CHANGE — did not move the needle on this corpus. Paraphrase category unchanged at 100%.
  - `+rewrite`: HURT (-11%) — a real negative result. Paraphrase category unchanged at 100%.
  - `all`: NO CHANGE — did not move the needle on this corpus. Paraphrase category unchanged at 100%.

## Caveats

- Retrieval latency here is wall-clock over a 13-document, in-memory
  index on one machine; treat the ms numbers as *relative* costs
  between configs, not production SLAs.
- The offline rewrites are scripted and deliberately weak (a mock
  cannot invent corpus vocabulary), so the offline multi-query row
  understates what a real LLM rewrite achieves — compare it to the
  headline run, not in isolation.
- hit@4 measures *retrieval* only. Whether the generator then uses the
  retrieved evidence faithfully is the Module 09 generation metrics'
  job, unchanged here.
