# Module 11 Lab — A Routing Support Agent, and the Six Ways It Breaks

## Scenario

TechCorp's support team is drowning in three kinds of question: quick calculations ("what's 17.5% of an $8,400 order?"), "where is my order?" lookups, and "what's the policy on…" questions. Your lead wants one agent that reads each incoming question, routes it to the right tool, and — crucially — behaves sensibly when things go wrong, because in production they will. You will wire the tools into a router and answer loop, then deliberately trigger the six failure modes support actually sees and make each one produce a clear message instead of a crash.

The tools already exist in `src/techcorp_agent/tools/` (you will reuse them in four later modules). Your job is `starter/agent.py`: the routing and answer loop.

## Learning objectives

By the end you can:

- Assemble tools into a router and select one per question (LLM routing with a deterministic fallback).
- Extract a tool's arguments from a raw question.
- Run a tool safely so every failure returns data, not an exception.
- Handle all six failure modes — ambiguous query, missing argument, timeout, no data, tool raising, wrong-tool selection — with a clear user-facing message.
- Explain why the tool *description* drives routing quality, and why these tools are read-only.

## Setup

```bash
uv sync                      # if you haven't already
```

Run commands from the repository root. Offline mode keeps the run deterministic:

- **Run your work:** `TECHCORP_OFFLINE=true uv run python course/11_tools_and_routing/starter/agent.py`
- **Test:** `uv run pytest course/11_tools_and_routing -q`
- **Peek at the target behavior:** `TECHCORP_OFFLINE=true uv run python course/11_tools_and_routing/solution/agent.py` (attempt each task first)

## Part A — Build the routing agent

Open `starter/agent.py`. Imports, the three tools (`build_tools`), the demo store, and the demo harness in `main()` are wired for you. Three TODOs remain.

### Task 1 — Read the tools

Open `src/techcorp_agent/tools/calculator.py`, `orders.py`, and `search_docs.py`. For each, find the `description` passed to `ToolSpec` and note how it ends by ruling out the *other* tools ("do NOT use for…"). Nothing to type — this is the idea from concepts §4, and you will feel it in Task 6.

### Task 2 — `extract_args(tool_name, question)`

Return the argument dict each tool needs:

- `calculator` → `{"expression": question}`
- `document_search` → `{"query": question}`
- `order_lookup` → find an order id in the question with `_ORDER_ID_RE`; return `{"order_id": <match>}` if found, else `{}` (empty — this is intentional and drives Task 5's missing-argument case).
- anything else → `{}`

### Task 3 — `answer(question, router_llm, answer_llm, tools)`

The routing/answer loop. `route_question(...)` is already called for you and gives a tool name. Finish it:

- If the name is `NO_TOOL`, return `answer_with_llm(question, answer_llm)`.
- Otherwise look the `ToolSpec` up by name, build its args with `extract_args`, and run it with `run_tool(tool, raw_args, timeout_seconds=TOOL_TIMEOUT_SECONDS)`.
- If `result.ok`, return `f"[{tool_name}] {result.output}"`; else return `f"[{tool_name} could not help] {result.error}"`.

### Task 4 — General questions (already wired)

`answer_with_llm` sends the question straight to the model. This is the `none` route: greetings, "explain what a warranty generally is," anything no tool should own. Confirm you call it in Task 3.

Run the agent (Checkpoint A). Four of the five demo questions should now route and run; the ambiguous one falls to the LLM.

## Part B — The six failure exercises

Each of these is a real support situation. For each, observe the behavior, then confirm the agent produces a clear message rather than a crash. Most are already visible in the demo run; the notes tell you how to trigger the rest.

### Exercise 1 — Ambiguous query

`"Can I return it?"` names no order and states no clear topic. The router returns `none`, and the agent asks a clarifying question via the LLM instead of guessing. Observe: no tool is called. Fallback: hand ambiguous questions to the model to ask for specifics — never route on a coin-flip.

### Exercise 2 — Missing required argument

`"Where is my order?"` routes to `order_lookup` (an order question) but contains no id, so `extract_args` returns `{}`. `run_tool` validates the empty args against the schema and returns `ok=False` naming the missing `order_id`. Observe: `[order_lookup could not help] Cannot run 'order_lookup' — missing required argument(s): order_id.` Try it by changing a demo question to drop the id.

### Exercise 3 — Tool timeout

`run_tool` accepts `timeout_seconds`. To see it fire, temporarily wrap a tool's `func` in one that sleeps longer than the timeout (there is a ready example in `tests/test_tools.py::test_run_tool_timeout`). Observe: `Tool 'x' timed out after 0.05s.` In production this is a stalled downstream API; the timeout keeps one slow tool from hanging the whole agent.

### Exercise 4 — Tool returns no data

`"What is the status of order TC-9999?"` routes and runs correctly, but no such order exists. `order_lookup` returns `ok=False` with a helpful message. Observe: `[order_lookup could not help] No order found with id 'TC-9999'...`. The same shape appears when `document_search` runs against an empty index. No-data is an outcome, not an error.

### Exercise 5 — Tool raises an exception

A tool with a bug (or unexpected input) can raise. `run_tool` catches any exception at the tool boundary and returns `Tool 'x' raised: <message>`. See `tests/test_tools.py::test_run_tool_catches_raising_tool`. The agent loop itself has *no* try/except around tool bodies — normalization happens once, in `run_tool`.

### Exercise 6 — Model selects the wrong tool

Scripted LLMs make this reproducible. In `main()`, change the router reply for the math question from `"calculator"` to a nonsense value like `"weather_tool"`. Because that is not a valid tool name, `route_question` ignores it and falls back to `keyword_route`, which reads the surface pattern and recovers. Observe: the math question still reaches the calculator. Fallback: the deterministic router is the floor the LLM can never fall through.

## Checkpoints

### Checkpoint A — the demo runs (offline)

`TECHCORP_OFFLINE=true uv run python course/11_tools_and_routing/solution/agent.py` prints:

```text
=== TechCorp routing agent (offline demo) ===

Q: What is 125 multiplied by 48?
A: [calculator] 6000

Q: What is the status of order TC-1234?
A: [order_lookup] Order TC-1234: status in_transit
last update: 2026-07-30T14:22:00Z
estimated delivery: 2026-08-06
items: AeroBook 14 Laptop, AeroDock USB-C Hub

Q: Can I return a damaged product?
A: [document_search] [support-warranty] (score 0.30) # Warranty Policy ...
[support-refund-damaged] (score 0.24) You do **not** need to return the damaged unit ...
...

Q: What is the status of order TC-9999?
A: [order_lookup could not help] No order found with id 'TC-9999'. Double-check the id (format TC-####) or ask the customer to confirm it.

Q: Can I return it?
A: Could you tell me which item or order you mean? I can then check.
```

Your starter must produce the same first line for each `Q:` once Tasks 2–4 are done. (Exact document-search snippets depend on the demo corpus; the routing and the `[calculator] 6000` / `in_transit` / `TC-9999 could not help` lines must match.)

### Checkpoint B — all six failure modes observed

You have seen, and can point to in the output or a test, each of: ambiguous (E1), missing argument (E2), timeout (E3), no data (E4), raise (E5), wrong-tool recovery (E6). None of them printed a traceback.

### Checkpoint C — tests green

```bash
uv run pytest course/11_tools_and_routing -q
uv run pytest tests/test_tools.py -q
```

Once your TODOs are gone, `test_my_work.py` runs (its skip disappearing is your progress bar) and everything passes.

## Debugging hints

- **`NotImplementedError: answer — see lab.md Task 3`** → you have not finished the routing loop yet. Work Tasks 2 then 3.
- **Math question prints `could not help ... invalid syntax`** → the calculator got prose it can't parse. It normalizes "multiplied by/times/plus" and strips `$`, `,`, and a leading "what is" — but not arbitrary sentences. `extract_args` for `calculator` should pass the whole question; the tool does the cleanup.
- **`KeyError` when looking the tool up by name** → build a `{tool.name: tool for tool in tools}` map; don't assume list order.
- **Wrong-tool exercise still routes wrong** → your reply string must not be a real tool name. `route_question` only falls back when the LLM reply is *not* a valid name (that is the whole point). `"weather_tool"` works; `"calculator "` (with a space) is normalized and still counts as valid.
- **`test_my_work.py` still skipping** → a `TODO` marker remains in `starter/agent.py`; the gate is literal.
- **Traceback from a slow/broken tool** → you called the tool's `func` directly instead of through `run_tool`; only `run_tool` provides the timeout and the catch.
- **`ModuleNotFoundError: techcorp_agent`** → run from the repo root with `uv run`, not from inside the module directory.

## Stretch exercise

1. **Add a fourth tool.** The instructions suggest an optional mock **weather** tool. Add `make_weather_tool()` returning canned data for a city, give it a precise description that rules out the others, and add a keyword-route rule (`"weather"`, `"forecast"`). Watch how the *description* alone changes the LLM's routing before you touch any keyword logic.
2. **Make a description worse on purpose.** Change the calculator's description to just `"does math"` and re-run a routing test with a borderline question. Note how selection quality drops — evidence for concepts §4.
3. **Run the eval dataset.** Load `data/evaluation/eval_dataset.json`, filter to `category == "tool_routing"`, and run each question through `keyword_route`. Two examples (`eval-027`, `eval-033`) it *cannot* get right from surface text alone — find them and explain why the LLM router exists.

When everything passes, go through [checklist.md](checklist.md).
