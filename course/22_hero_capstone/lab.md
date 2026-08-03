# Module 22 Lab — Integrate the TechCorp Knowledge Agent v2

## Scenario

Twenty-one modules of capabilities are sitting in `src/techcorp_agent/`: a
multi-agent supervisor, advanced retrieval, durable memory, streaming, an
approval gate, safety guardrails, tracing, and a production FastAPI service. Your
manager's message is short: *"IT signed off. Ship the production rollout — v2 —
this sprint."* Nothing new to invent. Your job is the last, hardest step:
**integration**. You will assemble the v2 agent yourself in
`starter/capstone_v2.py` by wiring the finished packages at their joints, then
verify it behaves identically to the shared-package graph
(`techcorp_agent.capstone_v2.build_v2_graph`) that the career docs describe.

Read [concepts.md](concepts.md) first, especially the architecture diagram and
the integration trade-offs — the lab makes you touch every joint it describes.

## Learning objectives

By the end you can:

1. **Integrate** twenty-one modules of components into one production graph
   without reimplementing any of them.
2. Wire durable **memory** (a SqliteSaver checkpointer) so a conversation
   survives a restart.
3. Drive a **human-approval interrupt** end to end: pause before a write, resume
   with a decision.
4. Enforce **safety at the boundary** with a session budget.
5. Capture a run with the **tracer** and stream the **event feed**.
6. Read the v2 **evaluation report** honestly and defend each integration
   trade-off.

## Setup check

```bash
TECHCORP_OFFLINE=true uv run python course/22_hero_capstone/solution/capstone_v2.py
```

You should see ten labelled interactions run offline (the real reference output
is captured below). Now open `course/22_hero_capstone/starter/capstone_v2.py` —
your copy has five gap areas, one per integration joint.

---

## Task 1 — Joint #1: build the graph with durable memory

Fill in `build_agent` and `ask`. The v2 graph is compiled with a checkpointer;
passing `build_v2_graph` a `db_path` gives you a durable SqliteSaver. Threading a
conversation is just `config={"configurable": {"thread_id": conversation_id}}`.

Run a policy question and a calculator question. Expected (real captured output):

```text
1) Policy route=policy sources=['hr-international-remote']
2) Calculator route=calculator answer='The result is 1470.'
```

Two things to notice in the trace (run the CLI with `--dev` to see it):

```text
[node=boundary] ok injection_findings=0
[node=supervisor] route=calculator reason=math
[node=calculator] backend=local ok=True
[node=formatter] route=calculator sources=[]
```

- The **supervisor** made the routing decision (Module 18). A math question is
  routed to the deterministic calculator before a specialist ever sees it.
- The **boundary** ran first (Module 20) — safety is on the untrusted edge.

**Debugging hint.** If your policy answer has empty `sources`, check that your
mock is scripted with a *routing reply first* (`"policy"`), then the grounded
answer. v2's supervisor spends one LLM call to route before the specialist
answers — that is the multi-agent cost, and it consumes the first scripted reply.

## Task 2 — Joint #2: drive the approval interrupt

Fill in `approve_ticket`. The ticket node calls `interrupt(...)` *before*
creating anything, so the first `invoke` pauses; you resume with
`Command(resume="approve" if approved else "reject")` on the same thread.

Expected:

```text
3) Approval created=True
```

Verify both branches: approve creates a `TCK-XXXX` ticket; reject creates nothing
("No ticket was created"). Notice the write only happens *after* the human
decides — a hallucinated ticket can never reach the support queue.

**Debugging hint.** If the first `invoke` already created the ticket (no pause),
you probably resumed in the wrong place. The paused result carries `INTERRUPT_KEY`
(`"__interrupt__"`); the ticket is created only on the *resume* invoke.

## Task 3 — Joint #3: run under a safety budget

`build_agent` already forwards a `budget` to `build_v2_graph`. Pass a zeroed
`SessionBudget(soft_limit_usd=0.0, hard_limit_usd=0.0)` and confirm the boundary
refuses the turn before any model call:

```text
4) Budget blocked=True
```

The boundary's `check_before_call()` fails closed — an exhausted session makes
zero further billable calls. That is budget enforcement at the edge (Module 20).

## Task 4 — Joint #4: capture a run with the tracer

Fill in `traced_run` using `traced_invoke` (the v2 analogue of Module 19's
`trace_agent`, which threads the checkpointer). It writes one JSON line per run:

```text
5) Traced answer='The result is 4.'
```

Confirm the trace file is non-empty — every node's step is captured from
`state["trace"]`.

## Task 5 — Joint #5: stream the event feed

Fill in `stream_run` using `stream_agent_events`. It normalizes the raw graph
stream into readable events:

```text
6) Streaming events=5
```

The real feed for `"What is 2+2?"`:

```text
  · node 'boundary' updated ['blocked', 'messages', 'trace']
  · node 'supervisor' updated ['route', 'trace']
  · route selected: calculator
  · node 'calculator' updated ['specialist', 'tool_result', 'trace']
  · node 'formatter' updated ['answer', 'messages', 'sources', 'trace']
```

This is the same normalizer the FastAPI service reuses to emit Server-Sent
Events — write it once, use it in the CLI and over HTTP.

---

## Run your finished assembly

```bash
TECHCORP_OFFLINE=true uv run python course/22_hero_capstone/starter/capstone_v2.py
```

Expected:

```text
1) Policy route=policy sources=['hr-international-remote']
2) Calculator route=calculator answer='The result is 1470.'
3) Approval created=True
4) Budget blocked=True
5) Traced answer='The result is 4.'
6) Streaming events=5
All integrated capabilities ran offline.
```

Then the tests stop skipping:

```bash
uv run pytest course/22_hero_capstone -q
```

---

## The reference, end to end

Running the solution walks every capability with real, captured output:

```text
--- 1) Policy (supervisor -> policy specialist, advanced RAG, cited) ---
A: Yes — up to 30 calendar days per year with manager approval and 60 days advance notice.
Sources: hr-international-remote
Route: policy

--- 2) Calculator (no document attribution) ---
A: The result is 1470.
Route: calculator

--- 3a) Order lookup (known) ---
A: Order TC-1234: status in_transit
...
Route: orders

--- 4) Unanswerable (abstention) ---
A: I do not have enough information in the provided TechCorp documents to answer that question.
Route: policy

--- 5) Multi-turn memory (survives a new graph on the same sqlite) ---
Follow-up answer: Longer stays need Legal and HR approval.
Follow-up prompt saw turn 1 history? True

--- 6) Approval gate (interrupt -> approve) ---
Paused before write? True
After approve: Created support ticket TCK-... for order TC-2048: ...

--- 8) Injection defense (blocked) ---
Blocked? True | I can't help with that request — it looks like an attempt to override...

--- 9) Budget hard-limit (refuse) ---
Blocked? True | Session budget exhausted: $0.0000 spent reaches the $0.0000 hard limit...
```

---

## The evaluation report

Regenerate the v2 report and read it honestly:

```bash
TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone_v2.report
# -> artifacts/capstone_v2_report.md
```

It has three parts: routing correctness (deterministic, ~75% offline — the same
keyword-collision misses as v1), retrieval metrics under the **advanced**
(hybrid+rerank) config with each example traced, and integration smoke checks for
memory / streaming / approval / injection / budget (all PASS offline).

---

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| Policy answer has empty `sources` | mock not scripted with a routing reply first | script `["policy", "<answer>\nSOURCES: ..."]` — the supervisor routes with an LLM call |
| Ticket created without pausing | resumed on the wrong invoke | the first invoke pauses (`INTERRUPT_KEY`); create only on the *resume* |
| `test_my_work` still skips | a `TODO` marker remains in `starter/` | remove every `raise NotImplementedError("TODO: ...")` line you filled |
| Follow-up ignores earlier turn | different `thread_id`, or a bare follow-up with no domain signal | reuse the same `conversation_id`; routing looks at the current utterance |
| `sqlite` errors on reuse | stale db in a shared temp path | tests use a fresh `tmp_path` per test; the CLI uses one durable file by design |

---

## Stretch goals

1. **Toggle advanced retrieval and compare.** Build two graphs, one with
   `advanced_rag=True` and one with `advanced_rag=False`, and diff their retrieval
   on the paraphrase examples. The Module 17 report predicts hybrid+rerank helps
   offline (60% → 100% on paraphrase) and is a wash on a live sentence-transformer
   corpus — reproduce that and write down which you'd ship and why.
2. **Add the optional web UI** in `apps/web/`: a single self-contained HTML page
   that POSTs to the v2 service's `/chat` (or reads `/chat/stream`) and renders the
   answer + sources. Keep it dependency-free.
3. **Trace a full conversation.** Wrap three turns of a thread with the tracer and
   inspect the run log — confirm the history recap grows and stays under budget.
