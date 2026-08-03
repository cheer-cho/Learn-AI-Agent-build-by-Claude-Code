[🗺 Course Roadmap](../../ROADMAP.html) · [← 17 Advanced RAG](../17_advanced_rag/README.md) · [19 Observability & Evaluation →](../19_observability_and_evaluation/README.md)

# Module 18 — Multi-Agent Systems

## Objective

Act 3 of the TechCorp story: policy, support, and order questions have grown
specialized enough that one agent juggling every tool and every policy in a
single prompt is starting to fumble. You will rebuild the v1 router as a
**supervisor** that delegates to three focused **specialists** — then do the
thing most multi-agent tutorials skip: **measure it honestly against the single
agent** on the evaluation dataset and decide, with numbers, whether the extra
machinery was worth it.

The headline lesson of this module: **multi-agent is a trade-off, not an
upgrade.** More agents is not more intelligence. It is more LLM calls, more
tokens, more latency, and a distributed-systems debugging problem — bought in
exchange for focus. Sometimes that trade pays off. Your job is to tell when.

## Difficulty

Advanced

## Prerequisites

- Module 11 (tools and routing — the `route_question` + `keyword_route`
  pattern, and the tool-confusion problem you will now attack structurally)
- Module 14 (the capstone single-agent graph you will compare against)
- Module 08 (the RAG pipeline the policy and support specialists retrieve with)
- No API key required — everything runs offline against the deterministic mock
  LLM and a hash-embedding store. Token and call counts are exact and
  repeatable offline; that is what makes the comparison meaningful with no key.

## What you will build

Working in `starter/multi_agent_lab.py`, you will **compose** already-built
pieces (you do not reimplement the specialists or supervisor):

1. Wire the **single-agent baseline** (`build_graph` from Module 14) behind a
   measurement wrapper that counts its LLM calls and tokens.
2. Wire the **supervisor** (`SupervisorAgent`) over the three specialists —
   `PolicySpecialist`, `SupportSpecialist`, `OrdersSpecialist` — and decide
   whether to enable the synthesis LLM call.
3. Run the **required comparison** (`run_comparison`) over a slice of the
   evaluation questions that exercises all three specialists.
4. Write the **comparison report** and answer, in writing:
   **"When would you ship the single agent instead?"**

The specialist/supervisor/comparison code lives in the shared library
(`src/techcorp_agent/agents/`) — read it, then use it.

## Files involved

```text
course/18_multi_agent/
├── README.md            ← you are here
├── concepts.md          ← read first: when one agent stops scaling, the
│                          supervisor pattern, shared vs private state, the
│                          real costs, and when NOT to go multi-agent
├── lab.md               ← the tasks + the required comparison table
├── starter/
│   └── multi_agent_lab.py   ← your working file (has TODO markers)
├── solution/
│   └── multi_agent_lab.py   ← reference implementation (runs offline)
├── tests/
│   ├── test_solution.py     ← proves the reference works (always runs)
│   └── test_my_work.py      ← your completion gate (skips until TODOs are gone)
└── checklist.md         ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/agents/` (specialists, supervisor, comparison),
`src/techcorp_agent/capstone/` (the Module 14 single agent),
`src/techcorp_agent/rag/pipeline.py`, `src/techcorp_agent/tools/`.

## Commands

```bash
# From the repository root.

# See the reference implementation run (works offline, prints the table):
TECHCORP_OFFLINE=true uv run python course/18_multi_agent/solution/multi_agent_lab.py

# Work the lab:
TECHCORP_OFFLINE=true uv run python course/18_multi_agent/starter/multi_agent_lab.py

# Test (offline; your tests skip until the TODOs are gone):
uv run pytest course/18_multi_agent -q

# The library-level tests for the agents package:
uv run pytest tests/test_multi_agent.py -q
```
