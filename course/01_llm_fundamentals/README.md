[🗺 Course Roadmap](../../ROADMAP.html) · [← 00 Setup](../00_setup/README.md) · [02 First API Call →](../02_first_api_call/README.md)

# Module 01 — LLM Fundamentals, Tokens, and Context

## Objective

Understand what a large language model actually does, how text becomes tokens, what a context window is, and why stuffing irrelevant text into a prompt hurts rather than helps. You will prove all of this to yourself by building a small **token-and-context explorer**.

## Difficulty

Beginner

## Prerequisites

- [Module 00 — Environment and Repository Setup](../00_setup/README.md) completed: `uv sync` done and `uv run pytest tests -q` passing.
- No API key required. This entire module runs offline.

## What you will build

A command-line **token-and-context explorer** (`explorer.py`) that:

1. Counts the tokens in any prompt (exactly with `tiktoken`, with a graceful heuristic fallback when the tokenizer can't load offline).
2. Reports token counts for a prompt before and after adding a configurable amount of irrelevant "noise" context.
3. Sends both versions to an LLM client and shows the responses side by side (a deterministic mock offline; optionally a real model if you configured a key).
4. Enforces a token budget — either rejecting oversized input with a clear, actionable error or truncating it to fit.

This is your first hands-on contact with the constraint that shapes the whole course: **models read a bounded window of tokens, and every token costs money and attention.** It is why Level 2 will teach retrieval.

## Files involved

```text
course/01_llm_fundamentals/
├── README.md            ← you are here
├── concepts.md          ← read this first
├── lab.md               ← then follow the tasks here
├── starter/explorer.py  ← your working file (has TODO markers)
├── solution/explorer.py ← reference implementation (peek only when stuck)
├── tests/test_solution.py  ← always runs; verifies the reference solution
├── tests/test_my_work.py   ← verifies YOUR starter once the TODOs are gone
└── checklist.md         ← self-check before moving on
```

Shared code you will import (already built for you in Module 00's repo):

- `src/techcorp_agent/schemas.py` — `ChatMessage`, `ChatResult`, `TokenUsage`
- `src/techcorp_agent/llm/factory.py` — `get_llm_client()` (mock offline, real client when a key is set)
- `src/techcorp_agent/llm/mock_client.py` — `MockLLMClient` (scripted, deterministic, records calls)

## Commands

Run everything from the repository root.

```bash
# 1. Read the concepts, then see the finished behavior:
uv run python course/01_llm_fundamentals/solution/explorer.py

# 2. Do the lab in the starter (see lab.md for the tasks):
uv run python course/01_llm_fundamentals/starter/explorer.py

# 3. Check your work (auto-skips until you remove the TODO markers):
uv run pytest course/01_llm_fundamentals/tests/test_my_work.py -q

# 4. Run the whole module's test suite:
uv run pytest course/01_llm_fundamentals -q
```

When all tests in step 3 pass, open [checklist.md](checklist.md).
