[🗺 Course Roadmap](../../ROADMAP.html) · [← 18 Multi-Agent](../18_multi_agent/README.md) · [20 Guardrails & Safety →](../20_guardrails_and_safety/README.md)

# Module 19 — Observability and Evaluation at Scale

## Objective

Act 3 of the TechCorp story: leadership no longer asks "can you build it?" — they ask "how do you **know** it works, and how do you know your last change didn't break it?" In this module you answer both. You instrument the capstone agent so every run leaves a **trace** (nodes visited, tools used, tokens, latency, final answer), you render those traces readably with no third-party account, and you turn the Module 09 evaluation dataset into a repeatable **experiment**. Then you deliberately worsen a prompt, re-run, and **catch the regression** in a before/after comparison — the concrete evidence behind "yes, this change is an improvement." Everything runs offline against a local JSONL trace log; LangSmith is the optional live path when you have a free key.

## Difficulty

Advanced

## Prerequisites

- Module 14 completed (you have the capstone graph: `build_graph`, `build_offline_store`)
- Module 09 completed (you built the deterministic evaluation metrics and read `artifacts/evaluation_report.md`)
- You understand hit@k, source accuracy, fact coverage, and the abstention contract
- No API key required — everything runs offline against hash embeddings and the mock LLM. A free `LANGSMITH_API_KEY` unlocks the optional live LangSmith path (Lab D).

## What you will build

You wire the shared `techcorp_agent.tracing` package into three labs in `starter/observability_lab.py`:

1. **Lab A — instrument and view.** Record real agent runs through `trace_agent` into `artifacts/traces/runs.jsonl`, then read them with `scripts/view_traces.py` (a rich table, plus `--run <id>` for one run's full step list).
2. **Lab B — dataset and baseline experiment.** Load the Module 09 dataset and run the grounded pipeline through `run_experiment`, reusing the deterministic metrics.
3. **Lab C — regression, caught.** Build a *worsened* pipeline that drops the citation rule — by composition, never editing shared code — re-run it, and `compare_experiments` names the regressed examples and the negative delta.
4. **Lab D — optional live.** With a free key, mirror the same runs to the LangSmith UI.

The tracer, the experiment runner, the regression comparison, and the LLM-judge live in the shared library `src/techcorp_agent/tracing/`. You read and wire them; the lab is about the *observability discipline*, not re-plumbing.

## Files involved

```text
course/19_observability_and_evaluation/
├── README.md            ← you are here
├── concepts.md          ← read first: traces/runs/spans, experiments, judge+deterministic, regressions
├── lab.md               ← the tasks (instrument → view → baseline → sabotage → catch)
├── starter/
│   └── observability_lab.py   ← your working file (has TODO markers)
├── solution/
│   └── observability_lab.py   ← reference implementation (runs Labs A-C offline)
├── tests/
│   ├── test_solution.py ← proves the reference works (always runs)
│   └── test_my_work.py  ← your completion gate (skips until the TODOs are gone)
└── checklist.md         ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/tracing/` (`tracer.py`, `experiments.py`, `judge.py`, `langsmith_bridge.py`), `src/techcorp_agent/capstone/` (`build_graph`, `build_offline_store`), `src/techcorp_agent/evaluation/` (`metrics.py`, `runner.py`), `data/evaluation/eval_dataset.json`, `scripts/view_traces.py`

## Commands

```bash
# From the repository root.

# See the reference labs run offline end to end (writes traces, catches the regression):
TECHCORP_OFFLINE=true uv run python course/19_observability_and_evaluation/solution/observability_lab.py

# View the traces it wrote:
uv run python scripts/view_traces.py
uv run python scripts/view_traces.py --run <run_id_prefix>

# Work the lab:
#   edit course/19_observability_and_evaluation/starter/observability_lab.py

# Test (offline by default; your tests skip until the TODOs are gone):
uv run pytest course/19_observability_and_evaluation -q

# Confirm the shared tracing library still passes too:
uv run pytest course/19_observability_and_evaluation tests/test_tracing.py -q
```

## Deliverable

`artifacts/traces/runs.jsonl` populated by instrumented runs, viewable through `scripts/view_traces.py`, and a regression comparison that names the examples a deliberate prompt change broke — the evidence that answers "how do you know your change improved the agent?"
