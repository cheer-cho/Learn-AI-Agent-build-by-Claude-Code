[🗺 Course Roadmap](../../ROADMAP.html) · [← 19 Observability & Evaluation](../19_observability_and_evaluation/README.md) · [21 Production Deployment →](../21_production_deployment/README.md)

# Module 20 — Guardrails, Safety, and Cost Control

> **Defensive security only.** Every attack in this module runs against *your
> own local lab system* so you can learn to protect it. Nothing here targets
> shared, production, or third-party systems, and the planted-attack documents
> in `data/security_lab/` never enter your main index.

## Objective

Treat everything your agent *reads* — retrieved documents and tool results — as
**untrusted input**, and build the guardrails that make that stance real:
detect and neutralize prompt injection planted in a document, validate answers
before they reach a user, and cap per-session cost so a runaway loop can't quietly
spend an unbounded bill.

By the end, when a security reviewer flags "a malicious document could hijack
the agent," you can point at the defenses that stop it and explain each one.

## Difficulty

Advanced

## Prerequisites

- Module 08 (RAG pipeline) — you harden its grounding contract here.
- Module 09 (grounding & evaluation) — citations and abstention are the output
  contract this module enforces.
- Module 11 (tools & routing) — read-only tools and allow-lists come up in the
  trust-boundary discussion.
- Module 15 (memory & persistence) — PII in stored conversations is part of the
  safety surface.
- No API key required — everything runs offline against the deterministic mock.

## What you will build

You COMPOSE an already-built safety toolkit (`src/techcorp_agent/safety/`) into
a lab script, `safety_lab.py`, that runs three labs:

1. **Lab A — injection demo + defense.** Load the planted expense-policy
   document, run an **unprotected** path (raw context, base prompt, a scripted
   hijacked model) that leaks order data, then a **protected** path (context
   demarcation + a hardened system prompt + output validation) that blocks the
   same leak. Record the before/after.
2. **Lab B — output validation.** Prove `validate_answer` catches a
   missing-citation answer and an invented-citation answer, and respects the
   abstention format.
3. **Lab C — budget enforcement.** A `SessionBudget` warns at a soft limit and
   refuses further model calls at a hard limit, with a clear user-facing message.

The shared toolkit you use (read, don't edit):

- `src/techcorp_agent/safety/injection.py` — `detect_injection`,
  `sanitize_context`, `harden_system_prompt`.
- `src/techcorp_agent/safety/validation.py` — `validate_question`,
  `validate_answer`.
- `src/techcorp_agent/safety/budget.py` — `SessionBudget`, `guarded_complete`,
  `BudgetExceeded`.

## Files involved

```text
course/20_guardrails_and_safety/
├── README.md            ← you are here
├── concepts.md          ← read first: the trust boundary, injection, validation, budgets
├── lab.md               ← the three labs, step by step
├── starter/
│   └── safety_lab.py    ← your working file (has TODO markers)
├── solution/
│   └── safety_lab.py    ← reference implementation (runs offline)
├── tests/
│   ├── test_solution.py ← proves the reference works (always runs)
│   └── test_my_work.py  ← your completion gate (skips until TODOs are gone)
└── checklist.md         ← acceptance criteria
```

## Commands

```bash
# From the repository root.

# See the reference run the before/after and the budget demo (works offline):
TECHCORP_OFFLINE=true uv run python course/20_guardrails_and_safety/solution/safety_lab.py

# Work the lab:
TECHCORP_OFFLINE=true uv run python course/20_guardrails_and_safety/starter/safety_lab.py

# Test (offline by default; your tests skip until the TODOs are gone):
uv run pytest course/20_guardrails_and_safety -q

# The safety toolkit's own unit tests:
uv run pytest tests/test_safety.py -q
```
