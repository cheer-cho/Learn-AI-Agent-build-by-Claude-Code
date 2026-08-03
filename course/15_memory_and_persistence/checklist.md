# Module 15 Checklist — Memory and Persistence

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words, why the v1 agent forgets everything (stateless invocations, no checkpointer, single-`question` state).
- [ ] I can distinguish **short-term memory** (one conversation, keyed by `thread_id`) from **long-term memory** (durable user facts, keyed by user) and say why they are separate mechanisms.
- [ ] I can explain what a **checkpointer** actually persists — the graph's state values, keyed by `thread_id` and checkpoint id — and what it does *not* (Python object identity, LLM memory, long-term facts).
- [ ] `starter/memory_lab.py` has no remaining `TODO` markers.
- [ ] `TECHCORP_OFFLINE=true uv run python course/15_memory_and_persistence/starter/memory_lab.py` runs offline end to end and prints, for Lab A, `follow-up prompt contained turn 1's question: True` and `persisted messages in thread: 4`.
- [ ] Lab A: I demonstrated a follow-up ("what if I stay longer than that?") resolving against an earlier turn, and the conversation continuing in a **brand-new graph on the same database file** (a simulated restart).
- [ ] Lab B: I applied a token budget and can point to the summary `system` message that replaced the older turns *and* the recent turns that were kept **verbatim** — and I can state the trade-off (fidelity for budget) in one sentence.
- [ ] I can explain why **memory is not the same as the context window**: the model is stateless; memory is what my application persists and replays into each prompt.
- [ ] Lab C: I stored durable facts in one session, recalled them after reopening the store (proving durability), and applied them on a **new thread** in a later session (`carried department: True`).
- [ ] I can name the privacy obligations of storing conversations — data minimization, retention limits, right to erasure (`UserMemoryStore.forget`), and thread/user isolation — and tie them to TechCorp's `data/privacy/` docs (GDPR).
- [ ] (Stretch) I inspected the `checkpoints` and `writes` tables with the `sqlite3` CLI and saw how `thread_id` drives both same-thread reload and cross-thread isolation.
- [ ] `uv run pytest course/15_memory_and_persistence -q` passes with `test_my_work.py` no longer skipped.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 15.
