[🗺 Course Roadmap](../../ROADMAP.html) · [← 15 Memory & Persistence](../15_memory_and_persistence/README.md) · [17 Advanced RAG →](../17_advanced_rag/README.md)

# Module 16 — Streaming and Human-in-the-Loop

## Objective

Act 3 of your TechCorp career: the agent works, but it *feels* dead. A question
lands, the terminal freezes for two seconds, then the whole answer drops at once.
And support wants the agent to open tickets — a real, outward-facing write that
must not fire on the model's say-so alone. You will make the agent feel alive by
**streaming** (tokens and workflow events) and make it safe by adding a
**human-in-the-loop approval gate** that pauses before creating a ticket and
resumes on a human decision — even after the process restarts.

## Difficulty

Advanced

## Prerequisites

- Module 14 completed (the capstone graph — `build_graph`, `build_offline_store`)
- Module 15 completed (persistence / checkpointers — the approval gate depends on
  one)
- Module 11's read-only-tools rule fresh in mind (this module adds the first
  *write* action and gates it)
- No API key required — everything runs offline against the deterministic mocks. A
  key only unlocks the optional live token-streaming demo.

## What you will build

Working against the `techcorp_agent.streaming` package (already built for you to
compose):

1. **Lab A — token streaming.** Stream a reply to the CLI chunk by chunk with
   `MockStreamingLLM` (offline) so the answer *types itself* instead of appearing
   all at once; `collect(...)` proves the chunks reassemble to the exact reply.
2. **Lab B — event streaming.** Wrap the real capstone graph in
   `stream_agent_events(...)` and watch the nodes light up in execution order —
   router, then a route node, then formatter — plus the route that was chosen.
3. **Lab C — approval gate.** Ask the agent to *create a support ticket for a
   damaged AeroBook order TC-2048*. The graph interrupts and shows exactly what
   will be created; you drive both the **approve** path (ticket id returned) and
   the **reject** path (nothing created, clear message).
4. **Lab D — resume after restart.** Re-open the same approval on a fresh graph
   backed by a temp Sqlite file, using the **same `thread_id`**, and finish the
   decision — proving the pending approval survived.

## Files involved

```text
course/16_streaming_and_hitl/
├── README.md            ← you are here
├── concepts.md          ← read first: perceived latency, stream modes, interrupts
├── lab.md               ← the four labs
├── starter/
│   └── streaming_lab.py ← your working file (has TODO markers)
├── solution/
│   └── streaming_lab.py ← reference implementation (runs offline)
├── tests/
│   ├── test_solution.py ← proves the reference works (always runs)
│   └── test_my_work.py  ← your completion gate (skips until TODOs are gone)
└── checklist.md         ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/streaming/` (`token_stream.py`, `events.py`, `approval.py`),
`src/techcorp_agent/capstone/` (`build_graph`, `build_offline_store`),
`src/techcorp_agent/llm/mock_client.py`.

## Commands

```bash
# From the repository root.

# See the reference implementation run all four labs (offline):
TECHCORP_OFFLINE=true uv run python course/16_streaming_and_hitl/solution/streaming_lab.py

# Work the lab:
uv run python course/16_streaming_and_hitl/starter/streaming_lab.py

# Test this module (offline; your tests skip until the TODOs are gone):
uv run pytest course/16_streaming_and_hitl -q

# Test the underlying streaming/HITL package:
uv run pytest tests/test_streaming_hitl.py -q

# Optional, with a real key in .env — live token streaming:
uv run python course/16_streaming_and_hitl/solution/streaming_lab.py --live
```
