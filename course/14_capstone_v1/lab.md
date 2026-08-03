# Module 14 Lab — Assemble the TechCorp Knowledge Agent v1

## Scenario

Thirteen modules of components are sitting in `src/techcorp_agent/`: a grounded
RAG pipeline, an evaluated retrieval stack, local tools, a router with a
deterministic fallback, two MCP servers, and a multi-server registry. Your
manager's message is short: *"Pilot team wants the knowledge agent Monday. Ship
v1."* Nothing new to invent — your job is the last, hardest step: **composition**.
You will assemble the agent graph yourself in `starter/capstone.py`, then verify
it behaves identically to the shared-package graph (`techcorp_agent.capstone`)
that Modules 15–22 build on.

Read [concepts.md](concepts.md) first, especially the architecture diagram and
the routing-fallback section — the lab makes you touch every joint it describes.

## Learning objectives

By the end you can:

1. Wire a LangGraph router with **conditional edges** to four capability nodes
   and one formatter.
2. Reuse the Module 11 router (LLM choice + `keyword_route` fallback) as a graph
   node, and explain which of the two actually routes when offline.
3. Implement **graceful degradation**: MCP when available, local tool or a clear
   "unavailable" answer when not — never a crash.
4. Enforce **honest provenance** in a single formatter: sources only for the
   retrieval route.
5. Walk all five required sample interactions offline and read the dev trace.

## Setup check

```bash
TECHCORP_OFFLINE=true uv run python course/14_capstone_v1/solution/capstone.py
```

You should see five interactions run offline. Now open
`course/14_capstone_v1/starter/capstone.py` — your copy has four TODO areas.

---

## Task 1 — The router node (TODO 1)

In `router_node`, pick a tool name and map it to a route.

- Call `route_question(question, llm, tools)` — it prompts the LLM to answer
  with exactly one tool name and **already falls back to
  `keyword_route(question, tools)`** whenever the reply is not a clean tool
  name. Add a `try/except` that falls back to `keyword_route` if the LLM call
  itself raises.
- Map the result: `document_search → ROUTE_RETRIEVAL`,
  `calculator → ROUTE_CALCULATOR`, `order_lookup → ROUTE_ORDERS`, anything else
  (including `"none"`) `→ ROUTE_GENERAL`.

**Checkpoint.** Offline, the mock LLM returns prose, never a tool name — so
every routing decision you'll see below is actually the *keyword fallback*
working. That is by design: the deterministic floor is what makes the agent
testable without a key.

## Task 2 — The conditional edges (TODO 2)

Wire the graph at the bottom of `build_agent`:

- `add_conditional_edges("router", route_selector, {...})` with all four
  routes mapped to their nodes.
- The retrieval node gets a **bounded retry seam**:
  `add_conditional_edges("retrieval", retrieval_decision, {"retry": "retrieval", "done": "formatter"})`.
  Look at `retrieval_decision` — the `max_loops` cap is checked *first*, so the
  loop is provably finite even if the answer never improves (Module 10, Lab D).
- `calculator`, `orders`, and `general` each go straight to `"formatter"`, and
  `"formatter"` goes to `END`.

**Checkpoint.** `TECHCORP_OFFLINE=true uv run python course/14_capstone_v1/starter/capstone.py`
should now *route* (watch the trace lines), even though the calculator and
formatter still print TODO text.

## Task 3 — The calculator fallback (TODO 3)

Finish `calculator_node`. The spec requires a math question to be answered
whether or not MCP is up:

1. If `_registry_has("calculator.add")`, try MCP first: parse a simple
   `A <op> B` and call `mcp_registry.call(f"calculator.{tool}", {"a": a, "b": b})`;
   use `result.structured_content["result"]` when `not result.is_error`.
2. Otherwise — no registry, server down, or the expression is more than a
   binary op (like a percentage) — run the **local** tool:
   `calculator_tool.run({"expression": question})`.

The reference for the MCP parse is
`techcorp_agent.capstone.graph._try_mcp_calculator`; reading it counts as
reuse, not cheating.

## Task 4 — The formatter rules (TODO 4)

Finish `formatter_node`. One output shape, honest provenance:

- **retrieval**: `answer = state["answer"]` (fall back to `ABSTENTION_TEXT` if
  empty), `sources = state["sources"]` — the only route allowed to carry
  sources;
- **calculator**: `answer = f"The result is {state['tool_result']}."`,
  `sources = []` — a computed number must never look like a document quote;
- **orders / general**: `answer = state["tool_result"]`, `sources = []`.

---

## Task 5 — Walk the five sample interactions

All TODOs gone? Run your assembly:

```bash
TECHCORP_OFFLINE=true uv run python course/14_capstone_v1/starter/capstone.py
```

Your output should match the reference run below (captured from
`solution/capstone.py`, byte-for-byte deterministic offline). For each one, read
the trace and make sure you can say *why* it took that path.

### 1) Policy question — retrieval + citation

```text
Q: Can an international employee work remotely from another country?
A: Yes - employees may work remotely from another country for up to 30 calendar days per year, with manager approval recorded before travel and 60 days advance notice; stays longer than 30 days additionally require joint Legal and HR approval.
Sources: hr-international-remote
Trace:
  [node=router] tool=document_search route=retrieval
  [node=retrieval] loop=1 chunks=4 abstained=False sources=['hr-international-remote']
  [node=formatter] route=retrieval sources=['hr-international-remote']
```

The grounded answer states the conditions (30-day cap, approval, notice) and
cites the document that holds them.

### 2) Semantic wording difference — "denim" vs "jeans"

```text
Q: Am I allowed to wear denim at headquarters?
A: Yes - jeans (denim) are allowed at headquarters as long as they are clean and free of rips, but not during client meetings.
Sources: hr-dress-code
Trace:
  [node=router] tool=document_search route=retrieval
  [node=retrieval] loop=1 chunks=4 abstained=False sources=['hr-dress-code']
  [node=formatter] route=retrieval sources=['hr-dress-code']
```

The policy never says "denim" in its rules text — it says "jeans" and "business
casual" — yet retrieval surfaces `hr-dress-code` anyway. Note the honest
caveat: offline, the *keyword* router would NOT have picked retrieval for this
phrasing ("denim" trips no policy keyword); the scripted mock plays the LLM
router's intent-based decision here, and the live-marked test in
`tests/test_capstone.py` proves a real LLM router does the same.

### 3) Calculator — and no document attribution

```text
Q: What is 17.5% of 8,400?
A: The result is 1470.
Trace:
  [node=router] tool=calculator route=calculator
  [node=calculator] backend=local ok=True
  [node=formatter] route=calculator sources=[]
```

`backend=local` because this run had no MCP registry; with the servers up the
same question shows `backend=mcp` for a plain `A * B` (percentages stay local —
the MCP server only exposes binary ops). Either way: `sources=[]`.

### 4) Order lookup — known and unknown

```text
Q: What is happening with order TC-1234?
A: Order TC-1234: status in_transit
last update: 2026-07-30T14:22:00Z
estimated delivery: 2026-08-06
items: AeroBook 14 Laptop, AeroDock USB-C Hub
Trace:
  [node=router] tool=order_lookup route=orders
  [node=orders] backend=local order=TC-1234 ok=True
  [node=formatter] route=orders sources=[]
```

```text
Q: What is happening with order TC-9999?
A: No order found with id 'TC-9999'. Double-check the id (format TC-####) or ask the customer to confirm it.
Trace:
  [node=router] tool=order_lookup route=orders
  [node=orders] backend=local order=TC-9999 ok=False
  [node=formatter] route=orders sources=[]
```

The unknown order is `ok=False` *data*, not an exception — the graph finishes
normally and the user gets an actionable message.

### 5) Unanswerable — abstention

```text
Q: What is TechCorp's policy for working from the Moon?
A: I do not have enough information in the provided TechCorp documents to answer that question.
Trace:
  [node=router] tool=document_search route=retrieval
  [node=retrieval] loop=1 chunks=4 abstained=True sources=[]
  [node=formatter] route=retrieval sources=[]
```

Look closely: `chunks=4`. Retrieval still returned its four nearest chunks —
they're just irrelevant. Abstention happened at *generation* time, and the
pipeline dropped all sources. "No evidence" ≠ "empty retrieval".

## Task 6 — The completion gate and the equivalence check

```bash
uv run pytest course/14_capstone_v1 -q          # test_my_work.py now runs
uv run pytest tests/test_capstone.py -q         # the shared-package suite
```

Then try the real CLI against the same graph your assembly mirrors:

```bash
TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone.cli \
    --question "What is 17.5% of 8,400?" --dev --no-mcp
TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone.report
```

Diff your trace lines against the CLI's `--dev` output — same nodes, same
decisions. Your assembly and the library are the same wiring.

## Debugging hints

- **Everything routes to `general`.** Your TODO 1 mapping is falling through.
  Print `tool_name` — offline the LLM reply is mock prose, so `route_question`
  must be returning the *keyword* decision; if you called the LLM directly
  instead of `route_question`, you lost the fallback.
- **`KeyError: 'retrieval'` (or similar) at invoke time.** Your conditional-edge
  path map doesn't cover every label `route_selector` can return. All four
  routes need an entry.
- **The graph never ends / recursion error.** Your retrieval retry edge loops
  without the bounded decision, or the cap check isn't first. Compare with
  `retrieval_decision` — cap first, then the retry condition.
- **Calculator answer contains mock text.** Your TODO 3 fell through to neither
  backend. Remember: no registry means `_registry_has(...)` is `False`, so the
  local tool must run unconditionally in that branch.
- **`sources` shows up on a calculator answer.** Your formatter is reading
  `state["sources"]` for every route. Retrieval writes that field; the formatter
  must only *forward* it for the retrieval route.
- **Order test hangs with MCP.** You are calling the async registry from graph
  code directly. Use the `SyncMCPRegistry` bridge (concepts.md §5) — an MCP
  session cannot be called from a different event loop than the one that
  created it.

## Stretch — a fourth tool route (weather)

Module 13 registered an optional `weather` server that fails to spawn, to prove
degradation. Extend *your* assembly the same way:

1. Add `ROUTE_WEATHER = "weather"` and a `weather_node` that calls
   `mcp_registry.call("weather.forecast", {"city": ...})` when
   `_registry_has("weather.forecast")`, else returns a clear "weather service
   unavailable" `tool_result`.
2. Route to it when the question contains a weather hint
   (`"weather"`, `"forecast"`, `"temperature"`) — extend your TODO 1 mapping and
   the TODO 2 path map with the fifth branch, and give the node an edge to
   `formatter`.
3. Ask "What's the weather where my order TC-1234 is?" — and notice the routing
   question it raises (order id *and* weather hint: which wins, and why?). Write
   your priority rule down; you have just designed a routing policy.

The point of the stretch: adding a capability touched the router map and one
node — the formatter, the state, and every other route were untouched. That is
what a composable agent buys you.
