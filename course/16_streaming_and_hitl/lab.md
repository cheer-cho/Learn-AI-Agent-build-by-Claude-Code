# Lab — Streaming and Human-in-the-Loop

## Scenario

Your TechCorp agent is correct but lifeless: every question freezes the terminal
until the full answer drops. And support has a new ask — let the agent open
tickets. That is a *write*: a real ticket a customer and a support team will act
on, and a hallucinated one is a mess someone has to clean up. So it needs a human
gate. In this lab you make the agent feel alive (streaming) and make it safe
(human-in-the-loop), working in `course/16_streaming_and_hitl/starter/streaming_lab.py`.

## Learning objectives

- Stream a reply to the CLI **token by token** so the answer types itself, and
  prove the chunks reassemble to the exact text.
- Stream **workflow events** and watch the graph's nodes light up in execution
  order, with the chosen route called out.
- Add an **approval gate**: interrupt before a write, show the human exactly what
  will happen, and drive both **approve** and **reject**.
- **Resume after a restart**: a fresh graph, backed by a Sqlite file, finishes a
  pending approval using the same `thread_id`.

## Before you start

Read the package you are composing (do not edit it):

- `src/techcorp_agent/streaming/token_stream.py` — `MockStreamingLLM`, `collect`.
- `src/techcorp_agent/streaming/events.py` — `stream_agent_events`, `AgentEvent`.
- `src/techcorp_agent/streaming/approval.py` — `build_approval_graph`,
  `start_ticket_request`, `resume_with_decision`, `PendingApproval`,
  `TicketResult`, `create_ticket`.

Everything runs offline. Run the reference first to see the target behavior:

```bash
TECHCORP_OFFLINE=true uv run python course/16_streaming_and_hitl/solution/streaming_lab.py
```

---

## Lab A — Token streaming

**Task.** Implement `stream_answer_to_cli(client, messages)`. Iterate over
`client.stream_complete(messages)`; for each chunk, append it to a list *and*
`print(chunk, end="", flush=True)` (the `end=""` keeps chunks on one line;
`flush=True` is what makes them appear immediately instead of being buffered).
After the loop, print a newline and return `collect(chunks)`.

**Why `flush=True` matters.** Without it, Python buffers stdout and you would see
the whole line at once anyway — defeating the point. Streaming's payoff is the
*flush per chunk*.

**Expected observable behavior** — the answer appears progressively, then:

```text
======================================================================
LAB A — Token streaming (the answer types itself)
======================================================================
  Q: Am I allowed to wear jeans under the dress code at headquarters?
  A: Yes — jeans are acceptable under TechCorp's business-casual dress code at headquarters, as long as they are clean and undamaged.
```

**Checkpoint.** `collect(chunks)` equals the full reply exactly. In a real
terminal you *see* it type out; in a test you assert the reassembly.

---

## Lab B — Workflow event streaming

**Task.** Implement `stream_workflow_events(graph, state)`. Iterate over
`stream_agent_events(graph, state)`; append each `AgentEvent` to a list and print
a readable line (e.g. `f"  · {event.summary}"`). Return the list.

**Expected observable behavior** — nodes light up in execution order, and the
route is called out on its own line:

```text
======================================================================
LAB B — Workflow event streaming (watch the nodes light up)
======================================================================
  Q: Am I allowed to wear jeans under the dress code at headquarters?
  · node 'router' updated ['route', 'trace']
  → route selected: retrieval
  · node 'retrieval' updated ['answer', 'evidence', 'loop_count', 'sources', 'trace']
  · node 'formatter' updated ['answer', 'sources', 'trace']
```

**Checkpoint.** `router` appears before `formatter`, and there is a `route`
event. That ordering is the whole point: you are watching the graph *think*.

---

## Lab C — Approval gate

**Task.** Implement `run_approval_gate(question, *, approve)`:

1. `pending = start_ticket_request(graph, question, thread_id)` — this runs the
   graph up to the `interrupt` in the ticket node and returns a `PendingApproval`.
   **No ticket has been created yet** — that is the safety guarantee.
2. Show `pending.payload` (action, summary, order id) — the exact effect.
3. `result = resume_with_decision(graph, pending.thread_id, approved=approve)` and
   return it.

**Expected observable behavior** — approve then reject:

```text
======================================================================
LAB C — Approval gate (a write needs a human yes/no)
======================================================================
  Q: Please create a support ticket for my damaged AeroBook order TC-2048.

  --- APPROVE path ---
  ⏸ APPROVAL REQUIRED — the agent wants to perform a write:
      action:   create_ticket
      summary:  Damaged AeroBook on delivery
      order id: TC-2048
      decision: APPROVE
  → Created support ticket TCK-93B2 for order TC-2048: Damaged AeroBook on delivery

  --- REJECT path ---
  ⏸ APPROVAL REQUIRED — the agent wants to perform a write:
      action:   create_ticket
      summary:  Damaged AeroBook on delivery
      order id: TC-2048
      decision: REJECT
  → No ticket was created — you rejected the request. Nothing was sent to the support system.
```

**Checkpoints.**
- On approve, `result.ticket_id` starts with `TCK-` and appears in the message.
- On reject, `result.ticket_id is None` and the message says nothing was created.
- The ticket id is deterministic (`create_ticket` hashes its inputs), so the same
  request always yields `TCK-93B2` here.

---

## Lab D — Resume after restart

**Task.** Implement `resume_after_restart(question)`. The scaffold already opens
two Sqlite connections to the same temp file to *simulate two processes*:

1. In "process 1", call `start_ticket_request(graph1, question, thread_id)` to
   pause and save the state; then `conn1.close()` (the process "exits").
2. In "process 2" — a brand-new `graph2` over the **same file** — call
   `resume_with_decision(graph2, thread_id, approved=True)`, close `conn2`, and
   return the result.

**Why this works.** The paused state (the prepared summary, the order id, the
position at the interrupt) lives in the Sqlite file keyed by `thread_id`, not in
any graph's memory. `graph2` never saw the request — it reads the pending
approval off disk. This is Module 15's checkpointer earning its keep.

**Expected observable behavior:**

```text
======================================================================
LAB D — Resume after restart (the pending approval survives)
======================================================================
  ⏸ process 1 paused, state saved to approvals.sqlite (thread=lab-d-durable)
     ...process 1 exits; nothing about this request is in memory now...
  → process 2 recovered the pending approval and finished: Created support ticket TCK-93B2 for order TC-2048: Damaged AeroBook on delivery
```

**Checkpoint.** `result.ticket_id` starts with `TCK-`, produced by a graph that
never ran the `prepare` step for this request — it came back from disk.

---

## Run it all

```bash
# The reference, all four labs, offline:
TECHCORP_OFFLINE=true uv run python course/16_streaming_and_hitl/solution/streaming_lab.py

# Your work:
uv run python course/16_streaming_and_hitl/starter/streaming_lab.py

# Tests (your test_my_work.py unskips once the TODOs are gone):
uv run pytest course/16_streaming_and_hitl -q
```

## Debugging hints

- **Lab A prints the whole line at once (no "typing" effect).** You dropped
  `flush=True`, or you built the string and printed it after the loop. Print
  *inside* the loop, per chunk, with `flush=True`.
- **`collect(chunks) != reply`.** You mutated or stripped chunks. Append them
  verbatim — the mock keeps whitespace attached so the join is exact.
- **Lab B: no `route` event / wrong order.** You are consuming `graph.stream`
  yourself instead of `stream_agent_events`, or reading a different `stream_mode`.
  Use the helper; it wraps `stream_mode="updates"`, which preserves node order.
- **Lab C returns a `TicketResult` from `start_ticket_request` (never pauses).**
  Your graph was compiled without a checkpointer, or you resumed before showing
  the payload. `build_approval_graph` *requires* a checkpointer and raises a clear
  `ValueError` if you pass `None`.
- **Lab C: a ticket appears before you approved.** The write must live *after*
  `interrupt(...)` in the node. In this lab the package already does that; if you
  see it, you called `create_ticket` yourself — don't. Let the graph do it on
  resume.
- **Lab D: `get_state`/resume finds nothing.** The two connections point at
  different files, or you used a different `thread_id`. Same file, same
  `thread_id` — that pair *is* the identity of a paused run.

## Stretch

Interleave **both** streams: run the capstone graph and, as each node's event
arrives, if that node produced answer text, stream *that text token by token*
before printing the next event. You will feel the two feeds' different rhythms —
events mark structure, tokens fill it in — and see exactly why they are separate
tools for separate consumers. (Hint: combine `stream_workflow_events` with a
`MockStreamingLLM` fed the node's output.)
