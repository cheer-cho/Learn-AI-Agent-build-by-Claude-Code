[🗺 Course Roadmap](../../ROADMAP.html) · [← 11 Tools & Routing](../11_tools_and_routing/README.md) · [13 Multi-Server MCP →](../13_multi_server_mcp/README.md)

# Module 12 — Model Context Protocol Fundamentals

## Objective

In Module 11 you gave one agent process its own hand-written tools. Now TechCorp
wants those capabilities to be *reusable* across many agents and apps without
copy-pasting Python. The industry answer is the **Model Context Protocol (MCP)**:
a standard way for an AI host to connect to independent tool *servers* over a
wire. In this module you build both sides of one connection — an MCP **server**
that exposes a calculator, and an MCP **client** that discovers and calls its
tools — and you learn exactly where MCP stops and where the host's control over
permissions, approval, and trust begins.

## Difficulty

Intermediate-Advanced

## Prerequisites

- Module 11 completed (you know what a tool wrapper / `ToolSpec` is and how an
  agent decides to call a tool).
- Comfortable with `async`/`await` — the MCP client API is asynchronous.
- No API key required. Everything in this module runs offline: the client
  spawns the server as a local subprocess and talks to it over stdio.

## What you will build

- **Lab A — a calculator MCP server** (`calculator_server.py`) exposing four
  typed tools: `add`, `subtract`, `multiply`, `divide`, with clear descriptions
  and a divide-by-zero guard that returns a proper error instead of crashing.
- **Lab B — an MCP client** (`mcp_client.py`) that starts/connects to the
  server, lists its tools, prints their JSON schemas, calls a chosen tool with
  arguments, and handles both server errors and validation errors.

By the end you can explain the difference between a plain Python function, a
tool wrapper, an MCP server, an MCP client, and an AI agent that uses an MCP
tool — the completion criterion for this module.

> **SDK note:** the installed `mcp` package is **version 2.0**. Its high-level
> server class is `mcp.server.MCPServer` — the successor to what `mcp` 1.x
> called `FastMCP` (imported from `mcp.server.fastmcp`, which no longer exists).
> The client uses `mcp.stdio_client` + `mcp.ClientSession`. See
> [concepts.md](concepts.md) for the exact API surface.

## Files involved

```text
course/12_mcp/
├── README.md              ← you are here
├── concepts.md            ← read first: host/client/server, schema, transport, trust
├── lab.md                 ← the two labs
├── starter/
│   ├── calculator_server.py  ← Lab A: FastMCP-style scaffold with TODO tool bodies
│   └── mcp_client.py         ← Lab B: client scaffold with TODOs
├── solution/
│   ├── calculator_server.py  ← reference server (runs offline)
│   └── mcp_client.py         ← reference client (spawns the server, runs offline)
├── tests/
│   ├── test_solution.py   ← proves the reference works (always runs)
│   └── test_my_work.py    ← your completion gate (skips until TODOs are gone)
└── checklist.md           ← acceptance criteria
```

Shared library you will also touch (read, don't edit here):
`src/techcorp_agent/mcp_servers/calculator_server.py` — the same server, promoted
to the shared library because Modules 13, 14, and 22 reuse it.

## Commands

```bash
# From the repository root.

# See the reference client run end-to-end, fully offline (it spawns the server):
uv run python course/12_mcp/solution/mcp_client.py

# Run the reusable shared server standalone over stdio (Ctrl-C to stop):
uv run python -m techcorp_agent.mcp_servers.calculator_server

# Work Lab A, then Lab B:
uv run python course/12_mcp/starter/mcp_client.py

# Test (offline; your tests skip until the TODOs are gone):
uv run pytest course/12_mcp -q

# Also exercise the shared-library server directly:
uv run pytest tests/test_mcp_calculator.py -q
```
