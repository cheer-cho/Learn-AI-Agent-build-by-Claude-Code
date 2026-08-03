[🗺 Course Roadmap](../../ROADMAP.html) · [← 08 RAG](../08_rag/README.md) · [10 LangGraph →](../10_langgraph/README.md)

# Module 09 — Grounding, Source Attribution, and Evaluation

## Objective

Stop trusting the RAG pipeline you built in Module 08 and start measuring it. TechCorp leadership wants a number, not a vibe: "how good is this assistant?" You will build the deterministic evaluation harness that answers that question — splitting the score into *retrieval* (did we fetch the required evidence?) and *generation* (did the answer use it faithfully?) — and produce a Markdown report leadership can actually read.

## Difficulty

Intermediate

## Prerequisites

- Module 08 completed (you have a working `RAGPipeline`: retrieve → augment → generate → cite)
- You understand chunks, embeddings, top-k retrieval, and the `SOURCES:` / abstention contract from Modules 06–08
- No API key required — the whole module runs offline against hash embeddings and the deterministic mock LLM. A key only makes the *generation* metrics meaningful (see the honesty note in the lab).

## What you will build

Four evaluation metrics and a report runner, in `starter/eval_lab.py`:

1. `hit_rate_at_k` — the RETRIEVAL metric: did an expected document land in the top-k retrieved chunks?
2. `source_accuracy` — a GENERATION metric: what fraction of the answer's citations were expected?
3. `fact_coverage` — a GENERATION metric: what fraction of the required facts appear in the answer (a deterministic substring approximation of completeness)?
4. `abstention_correct` — a GENERATION metric: did the system abstain exactly when it should have?
5. `run_and_report` — score every non-`tool_routing` example in `data/evaluation/eval_dataset.json`, aggregate overall and per category, and write `artifacts/evaluation_report.md`.

Your metric functions must behave identically to the permanent copies in `src/techcorp_agent/evaluation/` — later modules (17, 19) import *those* to re-run this exact evaluation and prove their upgrades moved the numbers.

## Files involved

```text
course/09_grounding_and_evaluation/
├── README.md            ← you are here
├── concepts.md          ← read first: the seven RAG failures, retrieval vs generation, the four metrics
├── lab.md               ← the tasks
├── starter/
│   └── eval_lab.py      ← your working file (has TODO markers)
├── solution/
│   ├── eval_lab.py      ← reference metrics + runner
│   └── run_eval.py      ← runs the evaluation over the real corpus, writes the report
├── tests/
│   ├── test_solution.py ← proves the reference works (always runs)
│   └── test_my_work.py  ← your completion gate (skips until TODOs are gone)
└── checklist.md         ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/evaluation/` (`metrics.py`, `runner.py`), `src/techcorp_agent/rag/pipeline.py`, `data/evaluation/eval_dataset.json`

## Commands

```bash
# From the repository root.

# See the reference evaluation run over the real corpus (works offline):
TECHCORP_OFFLINE=true uv run python course/09_grounding_and_evaluation/solution/run_eval.py

# Read the report it wrote:
#   artifacts/evaluation_report.md

# Work the lab:
#   edit course/09_grounding_and_evaluation/starter/eval_lab.py

# Test (offline by default; your tests skip until the TODOs are gone):
uv run pytest course/09_grounding_and_evaluation -q

# Confirm the shared evaluation package still passes too:
uv run pytest course/09_grounding_and_evaluation tests/test_evaluation.py -q
```
