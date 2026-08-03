[🗺 Course Roadmap](../../ROADMAP.html) · [← 21 Production Deployment](../21_production_deployment/README.md) · [🎓 Course complete!](../../ROADMAP.html)

# Module 22 — Hero Capstone: TechCorp Knowledge Agent v2

## Objective

This is the **Level 5 finale — HERO**. For twenty-one modules you built one
capability at a time: an LLM adapter, embeddings, a vector store, a grounded RAG
pipeline, an evaluation harness, a LangGraph, tools, MCP servers, durable memory,
streaming, an approval gate, a multi-agent supervisor, tracing, advanced
retrieval, guardrails, and a production FastAPI service. In Module 22 you **ship
the production rollout** that Act 3 of the story demands: **TechCorp Knowledge
Agent v2**, one deployable application that integrates all of it.

v2 is not a rewrite. It is the **integration** — the whole point of the course's
"build progressively" rule. v2 *reuses and composes* the packages you already
built and reimplements none of them. The mid-course v1 (Module 14) shipped to a
pilot with no memory, no streaming, no approvals, no observability, and plain
retrieval. v2 is what "production" means: the same agent, now with every Level-4
upgrade wired into one graph.

> **v1 → v2 in one line.** v1 was *composition of Modules 02–13*. v2 is
> *integration of the whole course* — v1's router-and-formatter graph, upgraded
> with the supervisor, advanced retrieval, durable memory, streaming, the
> approval gate, safety, and tracing, all behind one FastAPI service and CLI.

## Difficulty

Advanced / Capstone

## What v2 integrates (and where each piece comes from)

| Capability | Module | Package reused |
|---|---|---|
| Multi-agent supervisor routing | 18 | `agents/` (`SupervisorAgent`, specialists) |
| Advanced retrieval (hybrid + rerank) | 17 | `rag/advanced.py` |
| Durable multi-turn memory | 15 | `memory/` (`SqliteSaver` checkpointing) |
| Streaming (CLI + HTTP) | 16, 21 | `streaming/` (`stream_agent_events`) |
| Human approval for the ticket write | 16 | `streaming/approval.py` (`interrupt`) |
| MCP tools + graceful degradation | 12–14 | `mcp_servers/`, `capstone/mcp_bridge.py` |
| Guardrails, output validation, budget | 20 | `safety/` |
| Tracing + evaluation report | 19 | `tracing/`, `evaluation/` |
| FastAPI service, Docker, CI | 21 | reused patterns in `capstone_v2/app_service.py` |

The integrated code lives in the shared package
`src/techcorp_agent/capstone_v2/` — this is the codebase graders and the career
docs read. The lab has you assemble the same graph yourself in `starter/`.

## The four career documents live alongside this module

Module 22 is also where you package the project as a **career asset**. Four
documents sit in this directory and reference the real v2 code:

- `ARCHITECTURE.md` — the system design with Mermaid diagrams and the trade-off
  that justified every major decision.
- `DEMO_SCRIPT.md` — a five-minute live walkthrough for an interviewer.
- `PORTFOLIO_README.md` — a template to adapt when you publish the project.
- `INTERVIEW_PREP.md` — a question bank mapping each module to common
  AI-engineering interview questions, pointing at the code that answers each.

They are **authored separately** from this build (a different agent writes them),
so this README references them but does not contain them. Everything the code
needs to be documented accurately — the public API, the node names, the reuse
map — is what you assemble and verify in the lab.

## What you will build

- **Read + reuse the shared v2 package** (`src/techcorp_agent/capstone_v2/`):
  `state.py` (`V2State`), `graph.py` (`build_v2_graph`), `retrieval.py`
  (category-scoped hybrid+rerank), `checkpoint.py`, `app_service.py`
  (`build_v2_app`), `cli.py`, `report.py`.
- **The lab — assemble v2 yourself** (`starter/capstone_v2.py` →
  `solution/capstone_v2.py`): the starter imports every finished package and has
  TODO gaps at the *integration joints* — supervisor wiring, the memory
  checkpointer, the approval interrupt, the safety boundary, and tracing. You
  fill them in, then confirm your assembly behaves like the library
  `build_v2_graph`.

By the end you can explain — and demonstrate — how twenty-one modules of
components integrate into one production agent, and defend every integration
trade-off (advanced RAG on/off, multi-agent cost, memory footprint, approval
friction, safety overhead) with numbers from the evaluation report.

## Files involved

```text
course/22_hero_capstone/
├── README.md              ← you are here
├── concepts.md            ← read first: how every module composes; the architecture diagram; trade-offs
├── lab.md                 ← assemble v2 by wiring the finished packages; walk each capability with real output
├── starter/
│   └── capstone_v2.py     ← TODO-gapped assembly of the finished packages
├── solution/
│   └── capstone_v2.py     ← thin reference: builds + runs the shared-package v2 graph
├── tests/
│   ├── test_solution.py   ← proves the reference works (always runs)
│   └── test_my_work.py    ← your completion gate (skips until TODOs are gone)
├── checklist.md           ← the spec's capstone acceptance criteria + ROADMAP tick-off
├── ARCHITECTURE.md        ← career doc (authored separately)
├── DEMO_SCRIPT.md         ← career doc (authored separately)
├── PORTFOLIO_README.md    ← career doc (authored separately)
└── INTERVIEW_PREP.md      ← career doc (authored separately)
```

## Prerequisites

- **Modules 15–21** — you have built each Level-4 capability and can run each in
  isolation. v2 does not teach them again; it wires them together.
- **Module 14** — the v1 capstone graph (router → route nodes → formatter) and
  its five sample interactions, all of which v2 must still pass.
- No API key required. Everything runs offline against the mock LLM, hash
  embeddings, a tmp SQLite checkpointer, and local stdio MCP servers
  (`TECHCORP_OFFLINE=true`).

## Commands

```bash
# From the repository root.

# Ask one question, offline, with the dev trace and local tools (no MCP):
TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone_v2.cli \
    --question "What is 17.5% of 8,400?" --dev --no-mcp

# Interactive REPL — a durable multi-turn thread (spawns MCP; --no-mcp to skip):
uv run python -m techcorp_agent.capstone_v2.cli

# Stream the node-by-node event feed as the agent works:
uv run python -m techcorp_agent.capstone_v2.cli -q "How much vacation do I get?" --stream

# Run the v2 FastAPI service (offline, no Docker needed):
uv run uvicorn techcorp_agent.capstone_v2.app_service:app --reload

# See the reference lab assembly run end-to-end, fully offline:
TECHCORP_OFFLINE=true uv run python course/22_hero_capstone/solution/capstone_v2.py

# Regenerate the v2 evaluation report:
TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone_v2.report
# -> artifacts/capstone_v2_report.md

# Test (offline; your tests skip until the TODOs are gone):
uv run pytest course/22_hero_capstone -q
uv run pytest tests/test_capstone_v2.py -q
```
