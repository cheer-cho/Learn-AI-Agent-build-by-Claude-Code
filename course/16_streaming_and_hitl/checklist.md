# Module 16 Checklist — Streaming and Human-in-the-Loop

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words, the difference
      between **perceived** and **actual** latency, and why streaming improves the
      first but not the second.
- [ ] I can distinguish **token streaming** (answer text → the human) from **event
      streaming** (graph activity → a UI/monitor), and name which one a CLI reader
      vs a progress bar wants.
- [ ] I can state what each LangGraph `stream_mode` yields: `updates` (per-node
      delta), `values` (full accumulated state), `messages` (LLM tokens).
- [ ] **Lab A:** `stream_answer_to_cli` prints the reply progressively (with
      `flush=True`) and returns `collect(chunks)` equal to the exact reply.
- [ ] **Lab B:** `stream_workflow_events` yields the nodes in execution order
      (`router` before `formatter`) and a `route` event for the chosen path.
- [ ] I can explain why an **interrupt** pauses the graph and how `Command(resume=…)`
      makes `interrupt(...)` return the human's decision and continue the node.
- [ ] **Lab C — pause:** `start_ticket_request` returns a `PendingApproval` and the
      mock `create_ticket` has **not** been called yet.
- [ ] **Lab C — approve:** resuming with `approved=True` returns a `TicketResult`
      with a `TCK-` id that appears in the user-facing message.
- [ ] **Lab C — reject:** resuming with `approved=False` creates **no** ticket
      (`ticket_id is None`) and returns a clear "nothing was created" message.
- [ ] I can explain why resumable interrupts **require a checkpointer** (Module 15)
      and why `build_approval_graph(..., checkpointer=None)` is rejected.
- [ ] **Lab D:** a fresh Sqlite-backed graph resumes the **same `thread_id`** and
      finishes the approval — the pending decision survived the "restart".
- [ ] I can defend **which actions deserve approval** (writes, escalations,
      spending) and why the read-only routes stay un-gated (Module 11's rule).
- [ ] `starter/streaming_lab.py` has no remaining `TODO` markers.
- [ ] `uv run pytest course/16_streaming_and_hitl -q` passes with `test_my_work.py`
      no longer skipped.
- [ ] (Stretch) I interleaved event streaming and token streaming and can describe
      the different rhythms of the two feeds.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 16.
