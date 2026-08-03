[🗺 Course Roadmap](../../ROADMAP.html) · [← 14 Capstone v1](../14_capstone_v1/README.md) · [16 Streaming & HITL →](../16_streaming_and_hitl/README.md)

# Module 15 — Memory and Persistence

## Objective

The v1 pilot worked, and TechCorp wants to roll the assistant out company-wide. But pilot users hit the same wall every time: the agent forgets everything the instant it answers. Ask "Can I work remotely from Spain?" and then "What if I stay longer than that?" and it has no idea what *that* refers to. Employees expect a conversation, not a series of amnesiac one-shots.

In this module you give the capstone agent a memory — **without editing a single capstone file**. You add a SQLite *checkpointer* so a conversation continues across turns and survives an application restart; you keep the growing history under a token budget by *summarizing* older turns; and you add a *long-term store* of durable user facts (department, preferred answer length) that applies across separate sessions.

## Difficulty

Advanced

## Prerequisites

- Module 14 completed — you understand the capstone graph (`build_graph`: router → route nodes → formatter) and its stateless `AgentState`.
- Module 10 (LangGraph state and reducers) and Module 01 (tokens and the context window) — this module builds directly on both.
- No API key required — everything runs offline against the deterministic mock client and temporary SQLite databases.

## What you will build

A driver script, `memory_lab.py`, that exercises three new library capabilities (all living in `src/techcorp_agent/memory/`):

1. **A checkpointed conversation** — `build_memory_graph(...)` compiles the capstone graph with a `SqliteSaver`, and `ask(graph, question, thread_id)` runs one turn. Passing the same `thread_id` continues the conversation; a brand-new graph on the same database file continues it *after a restart*.
2. **Summarization under a budget** — `apply_budget(llm, messages, max_tokens)` returns `(messages, was_summarized)`: when the history would overflow the budget, older turns collapse into one summary message while the recent turns stay verbatim.
3. **Long-term preferences** — a `UserMemoryStore` (`remember` / `recall`, SQLite-backed) holds durable per-user facts, and `inject_preferences` prepends them to a prompt so a later, separate session answers with them in mind.

## Files involved

```text
course/15_memory_and_persistence/
├── README.md            ← you are here
├── concepts.md          ← read first: checkpointers, threads, trimming vs summarization, privacy
├── lab.md               ← the tasks (Labs A, B, C)
├── starter/
│   └── memory_lab.py    ← your working file (has TODO markers)
├── solution/
│   └── memory_lab.py    ← reference implementation (runs offline)
├── tests/
│   ├── test_solution.py ← proves the reference works (always runs)
│   └── test_my_work.py  ← your completion gate (skips until TODOs are gone)
└── checklist.md         ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/memory/` (`checkpointing.py`, `summarization.py`, `long_term.py`), `src/techcorp_agent/capstone/` (composed, never edited), `src/techcorp_agent/schemas.py`.

## Commands

```bash
# From the repository root.

# See the reference implementation run (works offline):
TECHCORP_OFFLINE=true uv run python course/15_memory_and_persistence/solution/memory_lab.py

# Work the lab:
TECHCORP_OFFLINE=true uv run python course/15_memory_and_persistence/starter/memory_lab.py

# Test (offline; your tests skip until the TODOs are gone):
uv run pytest course/15_memory_and_persistence -q

# Inspect the checkpoint tables the graph writes (stretch, see lab.md):
sqlite3 /path/to/conversation.db ".tables"
```
