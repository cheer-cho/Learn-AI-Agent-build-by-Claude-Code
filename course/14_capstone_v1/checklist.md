# Module 14 Checklist — Mid-Course Capstone: TechCorp Knowledge Agent v1

This is the Level 3 milestone, so the list below is the spec's **capstone
acceptance criteria** (the v1 items) restated as things *you* can check. Be
honest — Modules 15–22 build on exactly this system.

## Setup and reuse

- [ ] Setup works from a clean environment: `uv sync`, then
      `TECHCORP_OFFLINE=true uv run python course/14_capstone_v1/solution/capstone.py`
      runs with no API key and no network.
- [ ] I can name what the capstone **reuses** (corpus, embeddings, vector store,
      RAG pipeline + its prompts, graph state patterns, tools, router, MCP
      registry) and what little it adds (graph wiring, the sync MCP bridge, the
      CLI, the report) — and I can explain why reuse was the point.
- [ ] The vector index can be rebuilt: deleting `.chroma/capstone_v1` and
      re-running any entry point re-indexes the corpus automatically.

## The assembled graph

- [ ] My `starter/capstone.py` has **no TODO markers left**, and
      `uv run pytest course/14_capstone_v1 -q` passes with `test_my_work.py`
      no longer skipped.
- [ ] LangGraph **routes correctly**: policy → retrieval, math → calculator,
      order id → orders, chit-chat → general — and I can say which router
      (LLM or keyword fallback) made each decision offline.
- [ ] The RAG route **cites sources**, and only source ids that were actually
      in the retrieved context survive to the final answer.
- [ ] Unsupported questions trigger **abstention** ("working from the Moon"),
      and I can explain why `chunks=4` appears in that trace anyway
      (abstention is a generation-time decision, not empty retrieval).
- [ ] The formatter yields one consistent shape (answer + sources list) and
      **never attributes** a calculator or order result to the documents.
- [ ] The retrieval retry edge is **bounded**: the `max_loops` cap is checked
      first, so the graph is provably finite.

## MCP and degradation

- [ ] MCP tools are **discoverable and callable**: with the servers up, the
      calculator/orders traces show `backend=mcp`, and
      `tests/test_capstone.py::test_order_lookup_via_real_mcp_registry` passes.
- [ ] **Missing MCP servers do not crash unrelated flows**: with `--no-mcp`
      (or a failed spawn) math and order questions still answer via local
      tools, and an unavailable order system yields a clear message, not a
      traceback.
- [ ] An **unknown order** (TC-9999) returns a safe, actionable message.
- [ ] I can explain the `SyncMCPRegistry` bridge: why an MCP session must be
      driven from the event loop that created it, and how one background loop
      plus `run_coroutine_threadsafe` gives the sync graph a safe surface.

## Application behavior

- [ ] The CLI works both ways: one-shot `--question "..."` and the interactive
      REPL; a conversation id is generated and displayed when I don't pass one.
- [ ] **Dev mode vs user mode**: `--dev` shows the node-by-node trace; the
      default hides all internals.
- [ ] I know what v1 deliberately does **not** have — durable memory,
      streaming, approvals, observability, advanced retrieval — and which
      Level 4 module adds each (the CLI history is in-memory only; Module 15
      makes it persistent).

## Evaluation and tests

- [ ] `TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone.report`
      generates `artifacts/capstone_v1_report.md`, and I can read it honestly:
      routing accuracy is deterministic (keyword fallback), the two offline
      routing misses are keyword-collision artifacts, and only retrieval-side
      metrics are meaningful with the mock LLM.
- [ ] Automated tests pass offline:
      `uv run pytest course/14_capstone_v1 tests/test_capstone.py -q`.
- [ ] (Stretch) I added the optional weather route and can articulate the
      routing-priority rule I chose when an order id and a weather hint
      collide.

## Milestone

- [ ] v1 is something I could hand to a pilot team today — and I can describe,
      in one paragraph, the path from this codebase to the production v2
      (Modules 15–21, then the hero capstone in Module 22).
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 14.
