[🗺 Course Roadmap](../../ROADMAP.html) · [← 09 Grounding & Evaluation](../09_grounding_and_evaluation/README.md) · [11 Tools & Routing →](../11_tools_and_routing/README.md)

# Module 10 — LangGraph Fundamentals

## Objective

Stop writing your workflow as a straight line of function calls and start modeling it as a **graph**: named nodes that read and write one shared state, edges that decide what runs next, conditional edges that branch on a value, and loops that repeat under a strict cap. You will build the skeleton of TechCorp's GDPR policy-review workflow — retrieve, clean, analyze, find gaps, recommend, and retry retrieval when the evidence is thin — and make every step observable.

## Difficulty

Intermediate

## Prerequisites

- Module 02 completed (you can build a system + user message and call `get_llm_client()`)
- Module 08 completed (you have seen retrieval and grounding — Lab D models the "retry when evidence is insufficient" step)
- Comfortable with Python `TypedDict` and type hints
- No API key required — everything runs offline against the deterministic mock client

## What you will build

`starter/graphs.py`, four compiled LangGraph graphs, each with an observability trace:

1. **Lab A — Basic graph.** `Greeting → Enhancement → END`. The minimal shape: state, two nodes, three edges. (Given to you as the pattern.)
2. **Lab B — Draft and review.** `Outline → Draft → Review → Finalize`, each node one LLM call via `get_llm_client()`. Offline uses a scripted `MockLLMClient` so the output is exact.
3. **Lab C — Conditional route.** A classifier sends the request to either a short-explanation node or a detailed-policy-analysis node, based on a state field.
4. **Lab D — Iterative retrieval.** `analyze evidence → (retrieve more → analyze again)* → finalize`, with a **strict maximum-iteration cap** so the loop can never run forever.

Every solution graph prints a trace: node entered, state fields updated, route selected, iteration number, and final status.

## Files involved

```text
course/10_langgraph/
├── README.md            ← you are here
├── concepts.md          ← read first: graph, node, edge, state, loops, persistence
├── lab.md               ← the four labs
├── starter/
│   └── graphs.py        ← your working file (Lab A done; B/C/D have TODOs)
├── solution/
│   └── graphs.py        ← reference implementation (runs all four offline)
├── tests/
│   ├── test_solution.py ← proves the reference works (always runs)
│   └── test_my_work.py  ← your completion gate (skips until TODOs are gone)
└── checklist.md         ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/llm/factory.py` (`get_llm_client`), `src/techcorp_agent/llm/mock_client.py`, `src/techcorp_agent/schemas.py` (`ChatMessage`).

## Commands

```bash
# From the repository root.

# Setup (once, if you haven't):
uv sync
cp .env.example .env   # leave OPENAI_API_KEY blank to stay offline

# See the reference implementation run all four labs (works offline):
uv run python course/10_langgraph/solution/graphs.py

# Work the lab:
uv run python course/10_langgraph/starter/graphs.py

# Test (offline by default; your tests skip until the TODOs are gone):
uv run pytest course/10_langgraph -q
```
