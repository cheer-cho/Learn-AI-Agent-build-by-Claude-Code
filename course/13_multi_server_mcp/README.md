[🗺 Course Roadmap](../../ROADMAP.html) · [← 12 MCP](../12_mcp/README.md) · [14 Capstone v1 →](../14_capstone_v1/README.md)

# Module 13 — Multiple MCP Servers

## Objective

Module 12 connected one client to one server. Real hosts connect *several* at
once — a calculator here, an order service there, a docs server somewhere else —
and the moment you do, three problems appear that a single connection never had:
two servers can advertise a tool with the **same name** (a collision), a call
must be **routed** to the server that actually owns the tool, and one server
being **down** must not take the whole agent with it. In this module you build a
`MultiServerRegistry` that connects N servers, unifies their tools under
**namespaced** names, routes calls, reports **health**, and keeps operating when
a nonessential server fails — then wire an agent on top that sends math/orders to
MCP and policy questions to a *local* tool from Module 11.

## Difficulty

Intermediate-Advanced

## Prerequisites

- Module 12 completed — you can build an MCP server and an async stdio client,
  and you know why errors surface as `CallToolResult(is_error=True)`, not
  exceptions.
- Module 11 completed — you know what a local `ToolSpec` is and how a router
  picks one tool over another from its description.
- Comfortable with `async`/`await` and async context managers.
- No API key required. Everything runs offline: servers are local stdio
  subprocesses, and the agent's routing is deterministic (rule-based) so it runs
  with `TECHCORP_OFFLINE=true`.

## What you will build

- **The registry (shared library, read + reuse):**
  `src/techcorp_agent/mcp_servers/registry.py` — a `MultiServerRegistry` that
  registers servers, `connect_all()`s them (tolerating partial failure),
  `discover()`s a **namespaced** tool table (`calculator.multiply`,
  `orders.get_order_status`), `call()`s across servers, reports `health()`, and
  `aclose()`s cleanly.
- **A second server (shared library, read + reuse):**
  `src/techcorp_agent/mcp_servers/orders_server.py` — `get_order_status` and
  `list_recent_orders` over the mock order database, sitting beside the Module 12
  calculator server.
- **Lab — a multi-server agent** (`starter/multi_agent.py` → `solution/`): it
  connects both MCP servers via the registry, discovers their tools, folds in
  Module 11's **local** document-search tool, routes each question to the right
  place, returns every answer in one consistent format, and keeps working when
  the optional server is killed.

By the end you can explain — and demonstrate — namespacing, cross-server
routing, health reporting, and the essential-vs-nonessential partial-failure
policy that keeps a multi-server host alive.

> **SDK note:** the installed `mcp` package is **version 2.0** (server class
> `mcp.server.MCPServer`, client `mcp.stdio_client` + `mcp.ClientSession`,
> `tool.input_schema`, `CallToolResult.is_error`). Same surface as Module 12 —
> see [concepts.md](concepts.md).

## Files involved

```text
course/13_multi_server_mcp/
├── README.md              ← you are here
├── concepts.md            ← read first: collisions, namespacing, routing, health, partial failure
├── lab.md                 ← build the multi-server agent
├── starter/
│   └── multi_agent.py     ← TODO-marked wiring of registry + routing
├── solution/
│   └── multi_agent.py     ← reference agent (runs offline)
├── tests/
│   ├── test_solution.py   ← proves the reference works (always runs)
│   └── test_my_work.py    ← your completion gate (skips until TODOs are gone)
└── checklist.md           ← acceptance criteria
```

Shared library you also touch (read + reuse, don't edit here):

- `src/techcorp_agent/mcp_servers/registry.py` — the multi-server registry.
- `src/techcorp_agent/mcp_servers/orders_server.py` — the order-status server.
- `src/techcorp_agent/mcp_servers/calculator_server.py` — the Module 12 server, reused unchanged.
- `src/techcorp_agent/tools/search_docs.py` — the Module 11 local document-search tool.

## Commands

```bash
# From the repository root.

# See the reference multi-server agent run end-to-end, fully offline:
TECHCORP_OFFLINE=true uv run python course/13_multi_server_mcp/solution/multi_agent.py

# Run the two shared servers standalone over stdio (Ctrl-C to stop):
uv run python -m techcorp_agent.mcp_servers.calculator_server
uv run python -m techcorp_agent.mcp_servers.orders_server

# Work the lab, then run it:
TECHCORP_OFFLINE=true uv run python course/13_multi_server_mcp/starter/multi_agent.py

# Test (offline; your tests skip until the TODOs are gone):
uv run pytest course/13_multi_server_mcp -q

# Exercise the registry and both servers directly:
uv run pytest tests/test_mcp_registry.py tests/test_mcp_calculator.py -q
```
