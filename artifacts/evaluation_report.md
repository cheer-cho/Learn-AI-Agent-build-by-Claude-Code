# TechCorp RAG Evaluation Report

Deterministic evaluation of the Module 08 RAG pipeline against
`data/evaluation/eval_dataset.json`.

## Run context

- **embedding client**: sentence-transformers/all-MiniLM-L6-v2
- **llm**: mock-offline
- **k (retrieval depth scored)**: 4
- **documents indexed**: 13
- **examples evaluated**: 25
- **tool_routing examples skipped**: 8

`tool_routing` examples were excluded from this run: they require the
tool-using agent built in Level 3 (Module 11), not the RAG pipeline.

## Overall

| examples | hit rate@k | source accuracy | fact coverage | abstention accuracy |
|---:|---:|---:|---:|---:|
| 25 | 100% | 28% | 35% | 72% |

## Results by category

### ambiguous

| examples | hit rate@k | source accuracy | fact coverage | abstention accuracy |
|---:|---:|---:|---:|---:|
| 2 | 100% | 100% | 100% | 0% |

### answerable

| examples | hit rate@k | source accuracy | fact coverage | abstention accuracy |
|---:|---:|---:|---:|---:|
| 10 | 100% | 0% | 17% | 100% |

### multi_chunk

| examples | hit rate@k | source accuracy | fact coverage | abstention accuracy |
|---:|---:|---:|---:|---:|
| 3 | 100% | 0% | 0% | 100% |

### paraphrase

| examples | hit rate@k | source accuracy | fact coverage | abstention accuracy |
|---:|---:|---:|---:|---:|
| 5 | 100% | 0% | 0% | 100% |

### unanswerable

| examples | hit rate@k | source accuracy | fact coverage | abstention accuracy |
|---:|---:|---:|---:|---:|
| 5 | 100% | 100% | 100% | 0% |

## Reading these numbers honestly

- **Retrieval vs generation.** Hit rate@k judges only what the vector
  store returned; the other three judge what the model did with it.
  When the LLM in the run context is the offline mock, the
  generation-side numbers are placeholders that describe the mock,
  not any real model — only the retrieval numbers are meaningful.
- **Hash embeddings**, if used, match on word overlap only, so
  paraphrase questions fail retrieval by construction; real semantic
  embeddings score higher on that category.
- **Fact coverage is a substring check.** A correct paraphrase of an
  expected fact scores 0. Treat it as a floor, not a ceiling.
- **Hit rate is vacuously 1.0** for examples that expect no sources
  (unanswerable/ambiguous); those categories are judged by abstention
  accuracy instead.
- **All checks here are deterministic.** A model-based evaluator can
  be layered on top (Module 19), but never replaces these checks.
