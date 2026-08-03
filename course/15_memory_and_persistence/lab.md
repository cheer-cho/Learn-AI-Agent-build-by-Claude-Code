# Module 15 Lab — Give the TechCorp Agent a Memory

## Scenario

The v1 pilot is a hit, and leadership signed off on a company-wide rollout. Then the feedback arrived: employees hate that the assistant forgets. Priya asks whether she can work remotely from Spain, gets a good answer, asks "what if I stay longer than that?" — and the agent has no idea what *that* means. Your job this sprint is to make the assistant hold a conversation, keep that conversation from blowing the token budget, and remember durable facts about a user across sessions.

You will implement `starter/memory_lab.py`. The shared library (`src/techcorp_agent/memory/`) already provides the checkpointed graph, the budget helper, and the user-fact store — your job is to wire them together. **You will not edit any capstone file**; the memory graph *composes* the capstone's pipeline, router, and tools.

## Learning objectives

By the end you can:

- Compile the capstone graph with a SQLite checkpointer and drive a multi-turn conversation with a `thread_id`.
- Explain what a checkpointer persists and demonstrate a conversation surviving a restart.
- Apply a token budget: summarize older turns while keeping recent turns verbatim, and see the difference.
- Store durable user facts and apply them in a later, separate session.
- State the privacy obligations of storing conversation data.

## Setup

```bash
uv sync   # if you haven't already
```

Run commands from the repository root.

- **Run your work:** `TECHCORP_OFFLINE=true uv run python course/15_memory_and_persistence/starter/memory_lab.py`
- **Test:** `uv run pytest course/15_memory_and_persistence -q`
- **Peek at the target behavior:** `TECHCORP_OFFLINE=true uv run python course/15_memory_and_persistence/solution/memory_lab.py` (attempt each task first)

Read `concepts.md` before starting if you haven't.

## Tasks

Open `starter/memory_lab.py`. Each TODO maps to a step below.

### Lab A — Checkpointed conversations

This is the headline feature: a conversation that continues across turns and survives a restart.

**Step 1 — build a checkpointed graph and ask turn 1.** In `demo_checkpointed_conversation`, call `build_memory_graph(first_session, store, db_path)` to compile the capstone graph *with* a `SqliteSaver` persisting to `db_path`. Then `ask(graph, "Can I work remotely from Spain for a few weeks this autumn?", thread_id="priya-remote-work")`. The `thread_id` is the conversation's identity.

**Step 2 — restart, then ask the follow-up.** The starter `del`s the graph to simulate the process exiting. Build a **brand-new** graph on the **same** `db_path`, then `ask(...)` the follow-up "What if I stay longer than that?" on the **same** `thread_id`. If checkpointing works, the fresh graph reloads turn 1 from SQLite and the follow-up resolves against it.

Why this proves memory: the follow-up says "that" and nothing else. The only way to answer it is to have turn 1's context in the prompt — and turn 1 came from disk, in a different graph object.

### Lab B — Summarization under a budget

**Step — apply the budget.** In `demo_summarization_under_budget`, the history has two large early turns plus recent short ones, and the budget is a deliberately small `120` tokens. Call `apply_budget(summarizer, history, max_tokens=budget, keep_recent=4)`. It returns `(budgeted, was_summarized)`: older turns collapse into one summary `system` message; the four most recent turns are kept verbatim. Print the AFTER view so you can compare.

The point to internalize: summarization **trades fidelity for budget**. You spend one LLM call and lose some old detail to fit the conversation into the window — while keeping the recent turns (the ones a follow-up refers to) exact.

### Lab C — Long-term memory store

**Step 1 — remember durable facts.** In `demo_long_term_preferences`, open a `UserMemoryStore(user_db)` and `remember("priya", "department", "Engineering")` and `remember("priya", "preferred_answer_length", "short")`. Close it — that's the end of session 1.

**Step 2 — reopen and recall.** Open a **new** `UserMemoryStore` on the same `user_db` (a later session) and `recall("priya")`. Durability means the reopened store still has the facts.

**Step 3 — apply the preferences in a new session.** Build a memory graph and `ask(...)` a question on a **new** `thread_id`, passing `preferences=prefs`. The facts are injected into the prompt as a `system` note, so the agent answers with them in mind — in a conversation that has never seen Priya before.

## Checkpoints

### Checkpoint A — Lab A runs and remembers

`TECHCORP_OFFLINE=true uv run python course/15_memory_and_persistence/starter/memory_lab.py` prints (the mock is deterministic — your text matches):

```text
Turn 1  Q: Can I work remotely from Spain for a few weeks this autumn?
        A: Short international remote work is capped at 30 calendar days per year.

   (application restarted — new graph, same SQLite file)
Turn 2  Q: What if I stay longer than that?
        A: Beyond 30 days you need joint approval from Legal and HR.

   [check] follow-up prompt contained turn 1's question: True
   [check] persisted messages in thread: 4
```

`follow-up prompt contained turn 1's question: True` is the proof the follow-up saw the earlier turn. `persisted messages in thread: 4` is two full turns (user+assistant × 2) reloaded from disk.

### Checkpoint B — the budget is applied

Lab B prints a BEFORE and an AFTER. The BEFORE history is ~365 tokens against a 120 budget; the AFTER replaces the two big early turns with one `Summary of earlier conversation: …` message and keeps the last four verbatim:

```text
--- AFTER (summarized to fit the budget) ---
  system    Summary of earlier conversation: Earlier, the user asked for…
  user      Got it. How much advance notice do I need?
  assistant At least 60 days advance notice via the request form.
  user      And who approves stays over 30 days?
  assistant Joint approval from Legal and HR.
  estimated tokens: 90  (was_summarized=True)
```

The token count dropped below the budget and the recent turns survived word for word.

### Checkpoint C — preferences cross sessions

Lab C stores facts in session 1, reopens the store in session 2, and applies them on a fresh thread:

```text
Session 1: stored department=Engineering, preferred_answer_length=short

Session 2: recalled preferences {'department': 'Engineering', 'preferred_answer_length': 'short'}
        A: Hi Priya — happy to help.
   [check] prompt carried department: True
   [check] prompt carried length preference: True
```

`carried department: True` confirms the durable fact reached the new session's prompt.

### Checkpoint D — tests green

```bash
uv run pytest course/15_memory_and_persistence -q
```

Once your TODOs are gone, `test_my_work.py` stops skipping and joins `test_solution.py`. While TODO markers remain, `test_my_work.py` skips — that skip disappearing is your progress bar.

## Debugging hints

- **`NotImplementedError` with a task pointer** → that step is still a TODO. Implement it and remove the `raise`.
- **Follow-up ignores the earlier turn (`contained turn 1's question: False`)** → you used a different `thread_id` on turn 2, or built the second graph on a different `db_path`. Both must match turn 1 exactly.
- **`persisted messages` is 2, not 4** → you asked both turns but on different threads, so each thread has one turn. Same `thread_id` for both.
- **`StopIteration` / wrong answers from the mock** → the scripted `responses` list ran out or is misaligned. Remember a *retrieval* turn spends **two** replies: the router (`"document_search"`) then the answer. A *general* turn spends `"none"` then the reply.
- **Lab B `was_summarized=False`** → your history was already under the budget. Lower `max_tokens` or check you passed the big history, not a trimmed copy.
- **Lab C preferences not in the prompt** → you didn't pass `preferences=prefs` to `ask(...)`, or you recalled the wrong `user_id`.
- **`Deserializing unregistered type ...` warning** → you built a `SqliteSaver` without the library's serializer. Use `build_memory_graph`, which wires it for you; don't hand-roll the saver.
- **`ModuleNotFoundError: techcorp_agent`** → run from the repository root with `uv run`, not bare `python` inside the module directory.

## Stretch — inspect the SQLite checkpoint tables

The checkpointer is just SQLite. Point the driver at a real file (edit `main()` to use a fixed path instead of the temp dir, or add a `db=Path("conversation.db")` and run one turn), then open it:

```bash
sqlite3 conversation.db ".tables"
# checkpoints  writes

sqlite3 conversation.db "SELECT DISTINCT thread_id FROM checkpoints;"
# priya-remote-work

sqlite3 conversation.db "PRAGMA table_info(checkpoints);"
# thread_id | checkpoint_ns | checkpoint_id | parent_checkpoint_id | type | checkpoint | metadata
```

Notice: one `checkpoints` row per graph step (the state after each node), each tagged with `thread_id` — that is *exactly* how the same-thread reload and the cross-thread isolation work. The `writes` table records the per-node channel updates (the reducer inputs). Two different conversations are two different `thread_id` values in the same tables, which is why they never see each other.

Reflection: given what you now see on disk, what would TechCorp's Legal team want you to do about **retention** and **deletion** of these rows before a company-wide rollout? (Tie it back to `data/privacy/data_retention.md` and the `UserMemoryStore.forget` method.)

When everything passes, go through [checklist.md](checklist.md).
