[🗺 Course Roadmap](../../ROADMAP.html) · [← 07 Vector Databases](../07_vector_database/README.md) · [09 Grounding & Evaluation →](../09_grounding_and_evaluation/README.md)

# Module 08 — Retrieval-Augmented Generation

## Objective

Turn a vector store and an LLM into a grounded question-answering pipeline. You wire the three RAG stages — **retrieve** relevant chunks, **augment** the prompt with them, **generate** an answer that cites its sources — and, just as importantly, you make the pipeline *refuse* to answer when the evidence isn't there. By the end you will have rebuilt `techcorp_agent.rag.RAGPipeline` function by function and proven your version behaves identically to the shared library.

## Difficulty

Intermediate

## Prerequisites

- Module 05 (documents & chunking) — you know how a policy document becomes retrievable `Chunk`s.
- Module 06 (semantic search) — you understand embeddings and word-overlap similarity.
- Module 07 (vector databases) — you can index chunks into a `VectorStore` and query it with `top_k` and `min_score`.
- No API key required. Everything runs offline against deterministic hash embeddings and a scripted mock LLM. A key only makes the demo talk to a real provider.

## What you will build

`starter/my_rag.py`, a `MyRAGPipeline` class plus two helper functions, that:

1. `retrieve(question)` — vector-search the store, keeping only chunks above the similarity threshold.
2. `build_context_block(chunks)` — render each retrieved chunk as a `[source: <doc_id>]` section for the prompt.
3. `build_messages(question, chunks)` — assemble the grounded conversation: the system rules, the evidence, and the question.
4. `parse_answer(raw)` — split the model reply into `(answer_text, source_ids)` using the `SOURCES:` line protocol.
5. `answer(question)` — the full pipeline: retrieve, generate, parse, filter hallucinated citations, and detect abstention. When retrieval comes back empty, abstain **without** spending an LLM call.

The grounding contract (the `SYSTEM_PROMPT` and its five rules, and `ABSTENTION_TEXT`) is prewritten and imported from the shared library so your wording matches the tests character for character. The final task swaps your class for `techcorp_agent.rag.RAGPipeline` and confirms an identical `RAGAnswer`.

## Files involved

```text
course/08_rag/
├── README.md            ← you are here
├── concepts.md          ← read first: the three stages, the grounding contract, abstention
├── lab.md               ← the tasks
├── starter/
│   └── my_rag.py        ← your working file (has TODO markers)
├── solution/
│   ├── my_rag.py        ← reference implementation (runs offline)
│   └── demo.py          ← the six RAG scenarios over the real data/ corpus
├── tests/
│   ├── test_solution.py ← proves the reference works (always runs)
│   └── test_my_work.py  ← your completion gate (skips until TODOs are gone)
└── checklist.md         ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/rag/pipeline.py` (the reference contract), `src/techcorp_agent/vectorstore/chroma_store.py`, `src/techcorp_agent/schemas.py`, `src/techcorp_agent/llm/`, `src/techcorp_agent/embeddings/`.

## Commands

```bash
# From the repository root.

# See the reference pipeline run the six scenarios (works offline):
TECHCORP_OFFLINE=true uv run python course/08_rag/solution/demo.py

# See the smaller, step-by-step reference walkthrough (works offline):
uv run python course/08_rag/solution/my_rag.py

# Work the lab:
uv run python course/08_rag/starter/my_rag.py

# Test (offline by default; test_my_work.py skips until the TODOs are gone):
uv run pytest course/08_rag -q
```
