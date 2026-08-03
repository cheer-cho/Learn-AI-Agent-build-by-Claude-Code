# Module 10 Lab — Four Graphs for TechCorp

You will implement `starter/graphs.py`. **Lab A is already done** — read it first as the pattern, then build Labs B, C, and D. The observability helpers (`trace`, `print_trace`) and several scripted mock clients are given.

Everything runs offline against the deterministic mock client, so your output matches the checkpoints exactly.

## Setup

```bash
uv sync                      # if you haven't already
cp .env.example .env         # if you haven't already; blank key = offline mode
```

Run commands from the repository root.

- **Run your work:** `uv run python course/10_langgraph/starter/graphs.py`
- **Test:** `uv run pytest course/10_langgraph -q`
- **Peek at the target behavior:** `uv run python course/10_langgraph/solution/graphs.py` (attempt each lab before reading solution code)

Every lab prints a trace of the run. That trace *is* the observable output — read it after each checkpoint.

---

## Lab A — Basic graph (read this; it is implemented)

### Scenario

Before TechCorp trusts LangGraph with a compliance workflow, prove the smallest possible graph runs: a greeting node hands its message to an enhancement node, which finishes. `Greeting → Enhancement → END`.

### Objectives

- See a `TypedDict` state, two node functions returning **partial updates**, and `START` / `END` wiring.
- Understand the `trace` reducer: each node appends one line instead of overwriting.

### Walk the code

In `starter/graphs.py`, read `GreetingState`, `greeting_node`, `enhancement_node`, and `build_lab_a`. Note:

- Each node returns only the keys it changed (`greeting_node` returns `message` and `trace`, not `status`).
- `add_edge(START, "greeting")` sets the entry point; `add_edge("enhancement", END)` sets the end state.

### Checkpoint A

```bash
uv run python course/10_langgraph/starter/graphs.py
```

The first block prints:

```text
=== Lab A — Basic graph ===
  [node=greeting] message='Hello, Dana!'
  [node=enhancement] message='Hello, Dana! Welcome to TechCorp.'
  final status: complete
  message: Hello, Dana! Welcome to TechCorp.
```

…then it stops at Lab B's first `NotImplementedError`. That's expected — keep going.

---

## Lab B — Draft and review

### Scenario

TechCorp's docs team drafts policy summaries in stages: outline it, write a draft, review the draft, then finalize. Each stage is one LLM call. You will chain four nodes so state flows straight through: `Outline → Draft → Review → Finalize`.

### Objectives

- Build a four-node linear graph where each node calls the LLM.
- See **dependency injection**: the client is passed into `make_draft_graph(client)`, so tests can script exact replies.

### Steps

Find the three TODOs inside `make_draft_graph` and the wiring TODOs below them.

1. **`draft_node`** — call `_ask(client, <a writer system prompt>, "Write a draft from this outline:\n" + state["outline"])`. Return `{"draft": <result>, "trace": trace("draft", f"chars={len(<result>)}")}`.
2. **`review_node`** — same shape over `state["draft"]`; return `{"review": ..., "trace": trace("review", ...)}`.
3. **`finalize_node`** — `_ask` over `state["draft"]` **and** `state["review"]`; return `{"final": ..., "status": "finalized", "trace": trace("finalize", ...)}`.
4. **Wiring** — `add_node` for `draft`, `review`, `finalize`, then edges `outline → draft → review → finalize → END`.

The order of nodes in the graph must match the order the stages run — the edges, not the `add_node` calls, decide that.

### Checkpoint B

Re-run the starter. Lab B prints four stages in order and the finalized text:

```text
=== Lab B — Draft and review ===
  [node=outline] chars=53
  [node=draft] chars=66
  [node=review] chars=57
  [node=finalize] chars=136
  final status: finalized
  final text: GDPR is an EU data-protection regulation granting users rights such as access and erasure; TechCorp complies by honoring those requests.
```

The exact character counts come from the scripted `_scripted_draft_client()` — if yours differ, your edges are running the nodes out of order.

### Debugging hints

- **`KeyError: 'outline'` in `draft_node`** → you wired `draft` before `outline` (or skipped the `outline → draft` edge), so `state["outline"]` is still `""`. Check edge order.
- **Wrong `final text`** → `finalize_node` must read both `state["draft"]` and `state["review"]`. The scripted client returns replies in call order; a missing node call shifts every later reply.

---

## Lab C — Conditional route

### Scenario

The GDPR review starts by triaging the request: a quick factual question deserves a short explanation, but "analyze our retention policy for compliance gaps" needs the full policy-analysis branch. A classifier sets a state field, and a **conditional edge** routes to one of two nodes.

### Objectives

- Write a routing function that returns a **label**.
- Wire an `add_conditional_edges` with a path map, and see the two branches selected for two inputs.

### Steps

1. **`route_request`** — return `"detailed"` when `state["complexity"] == "complex"`, else `"short"`. (The classifier is given; it sets `complexity` from keywords.)
2. **`build_lab_c` wiring** — after the given `add_edge(START, "classify")`:
   - `graph.add_conditional_edges("classify", route_request, {"short": "short_explanation", "detailed": "detailed_policy_analysis"})`
   - `graph.add_edge("short_explanation", END)` and `graph.add_edge("detailed_policy_analysis", END)`
   - `return graph.compile()` (remove the `raise NotImplementedError`).

### Checkpoint C

Lab C runs two requests and prints the route each took:

```text
=== Lab C — Conditional route (simple request) ===
  [node=classify] complexity=simple
  [node=short_explanation] route=short
  final status: answered
  route: short  ...

=== Lab C — Conditional route (complex request) ===
  [node=classify] complexity=complex
  [node=detailed_policy_analysis] route=detailed
  final status: answered
  route: detailed  ...
```

Only one branch node appears in each trace — that is the conditional edge doing its job. If **both** ran, you added plain edges instead of a conditional one.

### Debugging hints

- **`KeyError` on a label** → the path map keys must exactly match what `route_request` returns (`"short"` / `"detailed"`). A typo like `"detail"` fails at routing time.
- **Both branches run** → you used `add_edge("classify", "short_explanation")` etc. Delete those; a conditional edge replaces them.

---

## Lab D — Iterative retrieval (with a strict cap)

### Scenario

The heart of the GDPR workflow. Analyze the evidence; if its score is below the threshold, retrieve more and analyze again — **but never loop forever.** A max-iteration cap stops the loop even when the evidence never improves. This is the spec's hard requirement.

### Objectives

- Write a loop-guard function with **two** stop conditions: threshold met **and** iteration cap reached.
- Wire a conditional edge plus a backward loop edge, and confirm the loop is finite.

### Steps

1. **`evidence_decision`** — return `"stop"` when `state["evidence_score"] >= state["threshold"]`; **also** return `"stop"` when `state["iteration"] >= state["max_iterations"]` (this is the infinite-loop guard); otherwise return `"retry"`.
2. **`build_lab_d` wiring** — after the given `add_edge(START, "analyze_evidence")`:
   - `graph.add_conditional_edges("analyze_evidence", evidence_decision, {"retry": "retrieve_more", "stop": "finalize"})`
   - `graph.add_edge("retrieve_more", "analyze_evidence")` — **the loop edge, pointing backward**
   - `graph.add_edge("finalize", END)`
   - `return graph.compile()` (remove the `raise NotImplementedError`).

`MAX_ITERATIONS = 3` and `EVIDENCE_THRESHOLD = 0.75` are given at the top of the section.

### Checkpoint D

Lab D runs twice — once where evidence never clears the bar (stops at the cap) and once where it passes on the second pass (stops early):

```text
=== Lab D — Iterative retrieval (evidence never improves) ===
  [node=analyze_evidence] iteration=1 score=0.20
  [node=retrieve_more] after iteration=1
  [node=analyze_evidence] iteration=2 score=0.30
  [node=retrieve_more] after iteration=2
  [node=analyze_evidence] iteration=3 score=0.40
  [node=finalize] status=max_iterations_reached
  final status: max_iterations_reached
  iterations: 3 (cap=3)

=== Lab D — Iterative retrieval (evidence passes) ===
  [node=analyze_evidence] iteration=1 score=0.40
  [node=retrieve_more] after iteration=1
  [node=analyze_evidence] iteration=2 score=0.90
  [node=finalize] status=sufficient_evidence
  final status: sufficient_evidence
  iterations: 2 (stopped early)
```

The first run **must** stop at `iteration=3` — `analyze_evidence` appears exactly three times. If your terminal hangs or the number climbs past 3, your cap check is missing or wrong.

### Debugging hints

- **`GraphRecursionError` / it never stops** → `evidence_decision` is missing the `iteration >= max_iterations` branch, so the loop only stops on a quality it never reaches. Add the cap check.
- **Stops after one pass every time** → you compared `iteration > max_iterations` (never true early) or returned `"stop"` unconditionally. Re-read the two conditions.
- **`KeyError: 'retrieve_more'`** → path map label mismatch: `evidence_decision` returns `"retry"`/`"stop"`, and the map must send `"retry"` to `retrieve_more` and `"stop"` to `finalize`.

---

## Checkpoint — tests green

```bash
uv run pytest course/10_langgraph -q
```

Once every TODO is gone, `test_my_work.py` stops skipping and all its tests pass — that skip disappearing is your progress bar. `test_solution.py` passes from the start (it tests the reference).

## Stretch exercises

1. **Real LLM for Lab B.** With a key in `.env`, call `main_lab_b(get_llm_client())` instead of the scripted client. The stages still run in order, but the text is now model-generated — and the character counts will differ every run. (Import `get_llm_client` from `techcorp_agent.llm.factory`.)
2. **Stream the run.** A compiled graph also has `.stream(state, stream_mode="updates")`, which yields one chunk per node as it finishes instead of only the final state. Wrap Lab A or Lab D in a `for chunk in app.stream(...)` loop and watch the state build up step by step — a preview of Module 16's streaming.
3. **Make the loop backstop fire.** Temporarily remove the `iteration >= max_iterations` check from `evidence_decision` and run Lab D with scores that never pass. Observe the `GraphRecursionError` LangGraph raises as its global backstop — then restore your clean cap and note the difference between a *crash* and a *graceful stop*.

When everything passes, go through [checklist.md](checklist.md).
