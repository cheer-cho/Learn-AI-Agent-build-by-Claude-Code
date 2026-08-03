# Module 12 Checklist — MCP Fundamentals

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words, the four roles:
      MCP **host**, **client**, **server**, and **tool** — and I can state the
      USB-C analogy *and* where it breaks (a connected server offers
      capabilities; it does not gain power).
- [ ] I can name MCP's three server capabilities — **tools, resources,
      prompts** — and say which the installed `mcp` 2.0 SDK supports (all three;
      this module uses tools).
- [ ] Lab A: `starter/calculator_server.py` has no remaining `TODO` markers and
      exposes `add`, `subtract`, `multiply`, `divide` as `@server.tool(...)`
      functions with typed `float` parameters and real descriptions.
- [ ] My `divide` rejects `b == 0` by raising `ValueError`, so the call returns
      `is_error=True` and the server does **not** crash.
- [ ] I understand the tool **schema**: types and descriptions are the contract
      the host/model reads to pick a tool and fill arguments, and in `mcp` 2.0 it
      lives on `tool.input_schema`.
- [ ] Lab B: `starter/mcp_client.py` has no remaining `TODO` markers and, run
      offline, connects, lists all four tools, prints their schemas, calls a
      tool, and handles errors.
- [ ] `uv run python course/12_mcp/starter/mcp_client.py` prints the four
      discovered tools with number-typed schemas, computes `multiply(125, 48) =
      6000.0`, and shows `is_error=True` for both a divide-by-zero and a
      wrong-typed argument — with **no traceback and no crash**.
- [ ] I know why errors surface as `CallToolResult(is_error=True)` rather than
      raised exceptions, and my client inspects `result.is_error`.
- [ ] I understand **transport**: this module uses **stdio** (the host launches
      the server as a subprocess, no network), and I can say when I'd choose HTTP
      instead.
- [ ] **Permissions & trust:** I can explain that MCP is *not* magical autonomy —
      the host still controls which servers are available, authentication,
      permissions/approval, logging, and error handling. Discoverable ≠
      permitted.
- [ ] I can articulate the trade-off: MCP's **reusability** across hosts vs the
      **permission and security requirements** each connected server imposes.
- [ ] (Stretch) I added a `power` tool to the server and watched the client
      discover it with **no client change**.
- [ ] `uv run pytest course/12_mcp -q` passes with `test_my_work.py` no longer
      skipped.
- [ ] **Completion criterion** — I can explain, out loud, the difference between:
      a **Python function**, a **tool wrapper** (Module 11 `ToolSpec`), an **MCP
      server**, an **MCP client**, and an **AI agent using an MCP tool** (see the
      table in `concepts.md` §9).
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 12.
