# Module 18 Lab — Build a Supervisor, Then Prove Whether It Was Worth It

You will build the three specialists into a supervisor, run the **required
comparison** against the Module 14 single agent on evaluation questions, read the
numbers, and answer in writing: **when would you ship the single agent
instead?**

Work in `starter/multi_agent_lab.py`. You are *composing* library pieces
(`techcorp_agent.agents`, `techcorp_agent.capstone`), not reimplementing them.

Run everything offline:

```bash
TECHCORP_OFFLINE=true uv run python course/18_multi_agent/starter/multi_agent_lab.py
uv run pytest course/18_multi_agent -q
```

---

## Task 0 — Read the pieces you are wiring

Before writing anything, read (do not edit):

- `src/techcorp_agent/agents/specialists.py` — how each specialist scopes its
  retrieval to a category allow-list and returns a `SpecialistResult` with its
  own call/token counts.
- `src/techcorp_agent/agents/supervisor.py` — `route` (LLM choice + keyword
  fallback), `synthesize` (pass-through vs an extra LLM call), and the graceful
  `try/except` in `answer`.
- `src/techcorp_agent/agents/comparison.py` — `run_comparison`,
  `write_comparison_report`, and the two `*_outcome` adapters.

## Task 1 — Wire the single-agent baseline (TODO 1)

Inside `single_agent_fn`, build the Module 14 graph over the shared store with
`mcp_registry=None`, invoke it on the question, and capture the final state.
Seed the state the way the capstone tests do:

```python
app = build_graph(llm, store, mcp_registry=None)
state = app.invoke({"conversation_id": "cmp", "question": question, "trace": [], "loop_count": 0})
```

The `_CountingMockLLM` wrapper (already written) totals the single agent's calls
and tokens for you.

## Task 2 — Build the supervisor (TODO 2)

Return a `SupervisorAgent(store, MockLLMClient(), synthesize_with_llm=...)`.
**Turn synthesis on** so the comparison shows the full cost of a realistic
multi-agent design (a routing call, the specialist's call, and a synthesis
call). Be ready to justify the choice.

## Task 3 — Run the required comparison (TODO 3)

Call `run_comparison(QUESTIONS, single_agent_fn(store), build_supervisor(store))`
and keep the returned dict. `QUESTIONS` already spans all three specialists
(two policy, two support, two orders) so the comparison is not one-sided.

## Task 4 — Write the report (TODO 4)

Write the markdown report with `write_comparison_report(results,
settings.artifacts_dir / "module18_comparison.md")` and print where it landed.

## Task 5 — Read the numbers and answer in writing (TODO 5)

Print the headline table and then answer, from `results["delta"]` and whether
the source columns match: **"When would you ship the single agent instead?"**

---

## What the reference run produces (real captured output)

Running the solution offline prints:

```text
=== Multi-Agent vs Single-Agent (offline, mock LLM) ===
metric                single    supervisor     delta
----------------------------------------------------
LLM calls                 10            16        +6
total tokens            5776          6262      +486
latency (s)           0.0273        0.0042   -0.0231
failures                   0             0        +0
```

As a table (the numbers your report will contain; latency varies run-to-run):

| metric | single agent | supervisor | delta |
|---|---:|---:|---:|
| LLM calls | 10 | 16 | **+6** |
| total tokens | 5776 | 6262 | **+486** |
| latency (s) | 0.0273 | 0.0042 | −0.0231 |
| failures | 0 | 0 | 0 |

Read these honestly:

- **The +6 LLM calls are the point.** Six questions, and the supervisor spent
  one extra *synthesis* call on each — on top of matching the single agent's
  route+answer calls. That is the multi-agent premium, and it is exact and
  repeatable offline. (Turn synthesis off and the supervisor *ties* the single
  agent on calls while still paying routing + latency overhead — a different,
  equally honest lesson.)
- **+486 tokens** is the same story in the other currency: more calls, more
  tokens, deterministically.
- **The negative offline latency is not a win for multi-agent.** Against the
  mock, model calls are free, so wall-clock time is dominated by *vector
  retrieval* — and the single-agent graph retrieves twice per RAG question,
  so it can clock *slower* offline despite making fewer calls. With a real
  network-bound LLM the extra calls dominate and the supervisor is the slower
  system. Trust the call/token deltas; treat offline latency as shape, not a
  benchmark.
- **Same failures (0/0), and offline both systems show empty source columns**
  because the echo mock emits no `SOURCES:` line — so on this offline slice the
  supervisor bought *nothing* over the single agent except cost. **That is a
  legitimate result, and it is the answer to Task 5:** on these questions, ship
  the single agent.

### So when *would* you ship the supervisor?

When you can show the specialist column doing something the single agent's
does not — a right citation the single prompt missed, or a lower failure rate on
a domain — or when the single prompt has grown too large to route reliably. You
prove that with *this same comparison*, run with a real LLM (or scripted answers
that emit real `SOURCES:` lines) so the quality columns become meaningful.

---

## Debugging hints

- **"My supervisor answered but `last_specialist` is wrong."** Offline the mock
  LLM never returns a valid specialist name, so routing falls through to
  `keyword_route`. Check that your question carries the surface signal you
  expect (an order id → orders; a support word like *refund/return/warranty* →
  support; otherwise → policy). This is by design, not a bug.
- **"A specialist returns no sources even though I scripted a `SOURCES:` line."**
  The pipeline only credits a source id that was actually in the retrieved
  chunks (the Module 08 honesty contract). If the id you cited was not among the
  category-scoped chunks that hash retrieval surfaced, it is correctly dropped.
  Print `specialist._rag.retrieve(question)` to see what was in scope.
- **"The supervisor's call count equals the single agent's."** You left
  synthesis off. Route + specialist = 2 calls, which *matches* a single agent
  that routes then answers. Turn synthesis on to see the premium.
- **"A specialist raised and my whole script died."** It should not — the
  supervisor catches specialist exceptions and returns a graceful apology with
  `failed=True`. If your script crashed, you probably called a specialist
  directly instead of going through `supervisor.answer(...)`.

---

## Stretch — a fourth specialist, and the routing confusion it introduces

Add a **PrivacySpecialist** scoped to just the `privacy` category (retention,
deletion, GDPR), and route privacy/GDPR questions to it. This deliberately
*overlaps* the existing PolicySpecialist, which already covers `privacy`.

Then measure the confusion it introduces (or does not):

1. Add `"privacy"` to the supervisor's valid names and keyword signals
   (`gdpr`, `deletion`, `retention` → privacy).
2. Re-run the comparison with a couple of privacy questions
   (e.g. eval-010, eval-031) and watch where they route.
3. Because `privacy` words now match *two* specialists' keyword sets, the order
   of your `if` checks decides the winner — a routing collision, exactly the
   Module 11 problem re-created by splitting one domain across two agents.

Write down what you observe: did the fourth specialist improve any answer, or
did it only add a routing ambiguity you then had to disambiguate by hand? That
observation *is* the lesson — more agents is not automatically more
intelligence, and an overlapping specialist can subtract clarity rather than add
it.
