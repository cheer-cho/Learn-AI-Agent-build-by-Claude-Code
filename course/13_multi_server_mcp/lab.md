# Module 13 Lab — Build a Multi-Server Agent

## Scenario

TechCorp's support agent needs three capabilities at once: arithmetic, live
order status, and answers grounded in company policy docs. Two of those already
exist as **MCP servers** (the Module 12 calculator, and a new orders server);
the third is a **local** in-process tool from Module 11 (`document_search`).
Your job is the host: connect both servers through one registry, present their
tools as a single namespaced menu, route each incoming question to the right
backend — MCP *or* local — and keep the agent answering even when an optional
server is down. You'll finish by killing that optional server and watching the
agent degrade gracefully instead of crashing.

You work one file: `starter/multi_agent.py`. The registry, both servers, and the
doc tool are already in the shared library — this lab is *wiring and routing*,
not reinventing them.

## Learning objectives

By the end you can:

- Connect multiple MCP servers through a `MultiServerRegistry` and discover a
  **unified, namespaced** tool table (`calculator.multiply`,
  `orders.get_order_status`).
- Route a question to the correct backend: MCP for math/orders, a local tool for
  policy docs — the capability decision vs the transport decision.
- Return every answer in one consistent format regardless of its source.
- Report per-server **health** and keep serving when a **nonessential** server
  fails (partial failure / graceful degradation).
- Explain why `document_search` stays local while the calculator and orders are
  servers.

## Setup

```bash
uv sync   # if you haven't already
```

Run all commands from the repository root.

- **See the target behavior first:**
  `TECHCORP_OFFLINE=true uv run python course/13_multi_server_mcp/solution/multi_agent.py`
- **Run your agent:**
  `TECHCORP_OFFLINE=true uv run python course/13_multi_server_mcp/starter/multi_agent.py`
- **Test:** `uv run pytest course/13_multi_server_mcp -q`

Attempt each task before reading the solution.

---

## Task 1 — routing (`route`)

Open `starter/multi_agent.py`. `route(question)` returns a `Route` describing
*where* a question goes. The pattern-matching is written for you; fill in each
`# TODO` to return the right `Route`, in this priority order:

1. **Order id present** (`TC-1234`) → `Route("mcp", "orders.get_order_status", {"order_id": ...})`
2. **Multiply pattern** (`125 x 48`, `125 multiplied by 48`) →
   `Route("mcp", "calculator.multiply", {"a": a, "b": b})`
3. **Weather hint** → `Route("mcp", "weather.forecast", {"city": "unknown"})`
   (this deliberately targets the *optional* server, which may be down)
4. **Doc/policy hint** (`return`, `warranty`, `damaged`, …) →
   `Route("local", "document_search", {"query": question})`
5. **Otherwise** → `Route("none", reason="…")`

Order matters: a concrete id or math expression is unambiguous and should win
over keyword hints.

## Task 2 — answering (`answer`)

`answer(question, registry, doc_tool)` calls `route`, invokes the right backend,
and formats the reply with `_format(source, ok, body)`. Fill the three branches:

- **`kind == "mcp"`** — `await registry.call(decision.tool, decision.args or {})`.
  The result is a `CallToolResult`; pull its text from `result.content[0].text`
  (guard for empty content), and return
  `_format(decision.tool, not result.is_error, text)`.
- **`kind == "local"`** — `tool_result = doc_tool.run(decision.args or {})`; return
  `_format("document_search", tool_result.ok, tool_result.output or tool_result.error)`.
- **`kind == "none"`** — return a formatted clarifying message with `ok=True`.

The rule that matters: **`answer` never raises.** A tool error, a down server, or
a missing document all come back as a formatted `unavailable` reply.

## Task 3 — wiring the demo (`run_demo`)

1. **Register three servers** on the `MultiServerRegistry`: `"calculator"` and
   `"orders"` (real), plus an optional `"weather"` via `missing_server_params()`
   with `essential=False`. The weather server is *meant* to fail to spawn — that's
   how you'll observe degradation.
2. Inside `async with registry:`, call
   `tools = await registry.connect_and_discover()`.
3. Print each server's **health** (`registry.health()`) and the **unified tool
   table**.
4. Loop the provided `questions` through `answer()` and print each `Q`/`A` pair.

## Required prompts

Your run must handle all of these (they're already in the starter's `questions`
list):

| Prompt | Expected route |
|---|---|
| `What is 125 multiplied by 48?` | `calculator.multiply` (MCP) → `6000.0` |
| `What is the status of order TC-1234?` | `orders.get_order_status` (MCP) → `in_transit` |
| `Can I return a damaged product?` | `document_search` (LOCAL) → retrieved policy text |
| `What is the status of order TC-9999?` | `orders.get_order_status` → graceful "no order found" |
| `What's the weather where my order is?` | `weather.forecast` → optional server **down**, clean "unavailable" |
| `Can I do that?` (intentionally ambiguous) | `none` → clarifying reply |

---

## Checkpoints

### Checkpoint A — servers connect and discovery is namespaced

Running the agent prints both real servers up, the optional one down, and a
6-tool unified table. This is the exact captured header from the reference run
(`TECHCORP_OFFLINE=true uv run python course/13_multi_server_mcp/solution/multi_agent.py`):

```text
=== TechCorp multi-server agent (offline demo) ===

Connected servers and health:
  - calculator  up, tools=4
  - orders      up, tools=2
  - weather     DOWN (Connection closed), tools=0

Unified tool table (6 tools):
  - calculator.add
  - calculator.divide
  - calculator.multiply
  - calculator.subtract
  - orders.get_order_status
  - orders.list_recent_orders
```

> A line like `can't open file '.../no_such_optional_server.py'` may appear
> **above** this output — that's the optional weather subprocess failing to
> spawn, printed to stderr by the child interpreter. It is expected: the
> registry catches the failure and marks `weather` DOWN. It is *not* a crash.

### Checkpoint B — every prompt routes correctly

The reference answers (captured, error section abbreviated):

```text
Q: What is 125 multiplied by 48?
A: [calculator.multiply | ok] 6000.0

Q: What is the status of order TC-1234?
A: [orders.get_order_status | ok] {
  "order_id": "TC-1234",
  "status": "in_transit",
  ...
}

Q: Can I return a damaged product?
A: [document_search | ok] [support-warranty] (score 0.30) # Warranty Policy ...

Q: What is the status of order TC-9999?
A: [orders.get_order_status | unavailable] Error executing tool get_order_status: No order found with id 'TC-9999'. ...

Q: What's the weather where my order is?
A: [weather.forecast | unavailable] Server 'weather' is unavailable (Connection closed); cannot call 'weather.forecast'.

Q: Can I do that?
A: [clarify | ok] I'm not sure whether that's a math, order, or policy question — could you add an order id (TC-####), the numbers, or the policy topic?
```

Read the shape: **every** answer — math, order, doc, two different failures, and
the clarification — comes back in the same `[source | ok|unavailable] body`
format. That's the "consistent format" requirement, and it's what lets a caller
handle all six the same way.

### Checkpoint C — the optional server being down changes nothing else

Two independent failures (an unknown order, a dead weather server) both surface
as `unavailable` replies, and the calculator and orders servers keep answering
perfectly. Kill the optional server (it's already killed — it never spawned) and
the agent is unaffected: that is graceful degradation.

### Checkpoint D — tests green

```bash
uv run pytest course/13_multi_server_mcp -q
```

Once your TODOs are gone, `test_my_work.py` stops skipping and must pass. Also
run the shared-library tests to confirm you're building on solid servers:

```bash
uv run pytest tests/test_mcp_registry.py tests/test_mcp_calculator.py -q
```

---

## Debugging hints

- **The client hangs forever** → the #1 async pitfall. The registry keeps each
  server's `stdio_client` / `ClientSession` context managers open for its whole
  lifetime; do all your work *inside* `async with registry:` and let it close on
  exit. Don't try to hold a `ClientSession` yourself, and don't call
  `registry.call(...)` after the `async with` block has exited — the sessions are
  gone.
- **`RuntimeError: no running event loop`** → run through `asyncio.run(run_demo())`
  (that's what `main()` does). Don't create a second event loop inside it.
- **`RuntimeError: Attempted to exit cancel scope in a different task`** on
  shutdown → you connected in one task and closed in another. Keep
  `connect_and_discover`, every `call`, and the `aclose` (via `async with`) in the
  *same* task. The reference does exactly this.
- **A weather question crashes instead of returning `unavailable`** → your `mcp`
  branch isn't inspecting `result.is_error`; the registry already returns a clean
  error result for a down server, so just format it. Never assume `call` raises.
- **`document_search` returns nothing** → the offline index is empty; make sure
  `_local_doc_tool()` ran (it builds a tiny hash-embedding index from the mock
  corpus on first use). This needs no API key.
- **The optional server shows `up` when it should be down** → you registered it
  with real params, or forgot `missing_server_params()`. It must point at a script
  that doesn't exist so the spawn fails.
- **Tests skip forever after you finished** → a literal `TODO` string remains in
  `starter/multi_agent.py`; the gate is literal. Delete the resolved markers.

## Stretch exercise — add a third (mock) server

Prove the registry scales past two servers with **no change to routing logic**.

1. Create a tiny third MCP server (copy the calculator's shape) that exposes one
   tool — say `forecast(city: str) -> str` returning a canned string like
   `"Sunny, 22°C in {city}"`. Put it in the shared library beside the others, or
   in your module's `starter/` for a quick experiment.
2. In `run_demo`, register it as `"weather"` with **real** params (and
   `essential=False`) instead of `missing_server_params()`.
3. Re-run. Now the weather prompt routes to a live `weather.forecast`, the health
   line shows `weather up, tools=1`, and the unified table has 7 tools — *you
   changed only the registration, not `route` or `answer`*.
4. Reflect: adding capability was one `register()` call. Now re-read
   concepts.md's trade-off — each new server is also a new process to trust,
   permission, and monitor. When is the third server worth it, and when is a
   local tool (like `document_search`) the better call?

When everything passes, go through [checklist.md](checklist.md).
