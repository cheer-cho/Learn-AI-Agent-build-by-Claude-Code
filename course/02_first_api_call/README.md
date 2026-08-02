[🗺 Course Roadmap](../../ROADMAP.html) · [← 01 LLM Fundamentals](../01_llm_fundamentals/README.md) · [03 LangChain →](../03_langchain/README.md)

# Module 02 — First LLM API Call

## Objective

Make your first scripted LLM call as TechCorp's newest junior AI engineer: read configuration from the environment, send a system + user message, and treat the response as what it really is — a rich object with content, metadata, and token usage — then turn that usage into an estimated cost.

## Difficulty

Beginner

## Prerequisites

- Module 00 completed (`uv sync` works, `.env` created from `.env.example`)
- Module 01 completed (you know what tokens are and have counted them with tiktoken)
- No API key required — everything in this module runs offline against the deterministic mock client. A key only unlocks the optional live test and the raw-SDK demo.

## What you will build

A script, `first_call.py`, that:

1. Loads settings (`techcorp_agent.config.Settings`) from the environment / `.env`
2. Gets an LLM client from the factory (mock offline, real provider with a key)
3. Sends a system message ("You are TechCorp's internal assistant.") plus a user question
4. Prints the assistant's reply
5. Safely inspects the full response object (model, finish reason, raw payload)
6. Extracts input / output / total token usage — without assuming usage exists
7. Estimates the request cost from the configurable per-1M-token rates
8. Handles authentication and network errors with messages that say what to fix

You will also study `solution/raw_sdk_demo.py`, the same call written directly against the raw `openai` SDK, to see exactly what the course adapter wraps.

## Files involved

```text
course/02_first_api_call/
├── README.md            ← you are here
├── concepts.md          ← read first: clients, roles, response anatomy, cost
├── lab.md               ← the tasks
├── starter/
│   └── first_call.py    ← your working file (has TODO markers)
├── solution/
│   ├── first_call.py    ← reference implementation (runs offline)
│   └── raw_sdk_demo.py  ← same call via the raw openai SDK (needs a key)
├── tests/
│   ├── test_solution.py ← proves the reference works (always runs)
│   └── test_my_work.py  ← your completion gate (skips until TODOs are gone)
└── checklist.md         ← acceptance criteria
```

Shared library code you will use (read, don't edit):
`src/techcorp_agent/config.py`, `src/techcorp_agent/schemas.py`, `src/techcorp_agent/costs.py`, `src/techcorp_agent/llm/`

## Commands

```bash
# From the repository root.

# Setup (once, if you haven't):
uv sync
cp .env.example .env   # leave OPENAI_API_KEY blank to stay offline

# See the reference implementation run (works offline):
uv run python course/02_first_api_call/solution/first_call.py

# Work the lab:
uv run python course/02_first_api_call/starter/first_call.py

# Test (offline by default; your tests skip until the TODOs are gone):
uv run pytest course/02_first_api_call -q

# Optional, with a real key in .env:
uv run python course/02_first_api_call/solution/raw_sdk_demo.py
uv run pytest course/02_first_api_call -m live -q
```
