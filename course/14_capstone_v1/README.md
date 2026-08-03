[🗺 Course Roadmap](../../ROADMAP.html) · [← 13 Multi-Server MCP](../13_multi_server_mcp/README.md) · [15 Memory & Persistence →](../15_memory_and_persistence/README.md)

# Module 14 — Mid-Course Capstone: TechCorp Knowledge Agent v1

## Objective

This is the **Level 3 milestone**. For thirteen modules you built one component
at a time — an LLM adapter, embeddings, a vector store, a RAG pipeline, an
evaluation harness, a LangGraph, tools, a router, MCP servers, a multi-server
registry. In Module 14 you **compose them into one coherent agent** and ship it
to a pilot team.

The whole point is **reuse**: the capstone *assembles* the shared library, it
does not reimplement anything. You wire a LangGraph that routes each question to
the right capability — grounded retrieval, a calculator, an order lookup, or a
plain LLM reply — formats every answer the same way, shows a developer trace on
demand, and **degrades gracefully** when a tool or MCP server is unavailable.

> **Where this sits.** v1 ships to a pilot team. It deliberately has **no**
> memory, streaming, human approvals, or observability yet — those are Level 4
> (Modules 15–21), which extend *this exact codebase* into the production
> **TechCorp Knowledge Agent v2** (Module 22). v1 is the foundation, not a
> throwaway demo.

## Difficulty

Advanced

## Prerequisites

- Modules 08–09 — you can build and evaluate a grounded RAG pipeline (cite
  sources, abstain when evidence is missing).
- Module 10 — LangGraph: `StateGraph`, conditional edges, an `operator.add`
  trace reducer, and a bounded loop.
- Module 11 — local tools (`ToolSpec`/`ToolResult`) and the LLM router with a
  deterministic keyword fallback.
- Modules 12–13 — MCP servers and the `MultiServerRegistry` (namespacing,
  partial failure, graceful degradation).
- No API key required. Everything runs offline against the mock LLM, hash
  embeddings, and local stdio MCP servers (`TECHCORP_OFFLINE=true`).

## What you will build

- **The shared capstone package (read + reuse):**
  `src/techcorp_agent/capstone/` — `state.py` (the `AgentState`), `graph.py`
  (`build_graph`: router → retrieval / calculator / orders / general →
  formatter), `mcp_bridge.py` (a synchronous bridge to the async MCP registry),
  `cli.py`, and `report.py`. This is the package Modules 15–22 extend.
- **The lab — assemble your own capstone** (`starter/capstone.py` →
  `solution/capstone.py`): the starter imports every pre-built component and has
  TODO gaps at the interesting joints (router wiring, the conditional edges, the
  formatter rules, the MCP-vs-local fallback). You fill them in, then confirm
  your assembled agent behaves identically to the library `build_graph`.

By the end you can explain — and demonstrate — how retrieval, tools, MCP, and a
LangGraph state machine compose into one agent, and how graceful degradation and
a dev-vs-user trace keep it operable.

## Files involved

```text
course/14_capstone_v1/
├── README.md              ← you are here
├── concepts.md            ← read first: composition, routing+fallback, degradation, dev/user, what v1 lacks
├── lab.md                 ← assemble the capstone, walk the five sample interactions
├── starter/
│   └── capstone.py        ← TODO-gapped assembly of the pre-built components
├── solution/
│   └── capstone.py        ← thin reference: builds + runs the shared-package graph
├── tests/
│   ├── test_solution.py   ← proves the reference works (always runs)
│   └── test_my_work.py    ← your completion gate (skips until TODOs are gone)
└── checklist.md           ← v1 acceptance criteria + ROADMAP tick-off
```

Shared library you assemble (read + reuse, don't edit here):

- `src/techcorp_agent/capstone/graph.py` — `build_graph` and the nodes.
- `src/techcorp_agent/capstone/state.py` — the `AgentState`.
- `src/techcorp_agent/capstone/mcp_bridge.py` — `SyncMCPRegistry`.
- `src/techcorp_agent/rag/pipeline.py`, `tools/`, `mcp_servers/`, `evaluation/`.

## Commands

```bash
# From the repository root.

# Ask one question, offline, with the dev trace and local tools:
TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone.cli \
    --question "What is 17.5% of 8,400?" --dev --no-mcp

# Interactive REPL (spawns the MCP servers; --no-mcp to skip them):
uv run python -m techcorp_agent.capstone.cli

# See the reference lab assembly run end-to-end, fully offline:
TECHCORP_OFFLINE=true uv run python course/14_capstone_v1/solution/capstone.py

# Regenerate the evaluation report:
TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone.report
# -> artifacts/capstone_v1_report.md

# Test (offline; your tests skip until the TODOs are gone):
uv run pytest course/14_capstone_v1 -q
uv run pytest tests/test_capstone.py -q
```
