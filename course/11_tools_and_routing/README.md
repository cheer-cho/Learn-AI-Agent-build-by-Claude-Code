[🗺 Course Roadmap](../../ROADMAP.html) · [← 10 LangGraph](../10_langgraph/README.md) · [12 MCP →](../12_mcp/README.md)

# Module 11 — Tools and Intelligent Routing

## Objective

Give the TechCorp agent hands. Until now it could only talk; here it learns to *do* — evaluate arithmetic, look up a specific order, and search company documents — by choosing the right tool for each question and running it safely. You will build a small tool interface, three real tools, and a router that decides which one (if any) to call, then handle the six ways this goes wrong in practice.

## Difficulty

Intermediate

## Prerequisites

- Module 08 completed (you understand retrieval and the `VectorStore`)
- Module 10 completed (you have seen an agent as a graph of steps)
- No API key required — everything runs offline. The router LLM is scripted in the demo so the run is deterministic; the tools execute for real.

## What you will build

A routing research/support agent (`agent.py`) that, for each question:

1. Asks the router to pick one tool — `calculator`, `order_lookup`, `document_search`, or `none`.
2. Extracts the argument that tool needs from the question.
3. Runs the tool through a safe executor (argument validation + timeout) that turns every failure into data, not a crash.
4. Phrases the tool's result — success *or* failure — back to the user, or answers directly with the LLM when no tool fits.

The tools themselves live in the shared package `src/techcorp_agent/tools/` (reused by Modules 13, 14, 18, and 22). You wire them together here.

## Files involved

```text
course/11_tools_and_routing/
├── README.md            ← you are here
├── concepts.md          ← read first: tools, descriptions, routing, results, safety
├── lab.md               ← the tasks (incl. the six failure exercises)
├── starter/
│   └── agent.py         ← your working file (has TODO markers)
├── solution/
│   └── agent.py         ← reference implementation (runs offline)
├── tests/
│   ├── test_solution.py ← proves the reference works (always runs)
│   └── test_my_work.py  ← your completion gate (skips until TODOs are gone)
└── checklist.md         ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/tools/` (`base.py`, `calculator.py`, `orders.py`, `search_docs.py`, `router.py`), `src/techcorp_agent/vectorstore/`, `src/techcorp_agent/llm/`.

## Commands

```bash
# From the repository root.

# See the reference implementation run (offline, deterministic):
TECHCORP_OFFLINE=true uv run python course/11_tools_and_routing/solution/agent.py

# Work the lab:
TECHCORP_OFFLINE=true uv run python course/11_tools_and_routing/starter/agent.py

# Test (offline by default; your tests skip until the TODOs are gone):
uv run pytest course/11_tools_and_routing -q

# Exercise the shared tools directly:
uv run pytest tests/test_tools.py -q
```
