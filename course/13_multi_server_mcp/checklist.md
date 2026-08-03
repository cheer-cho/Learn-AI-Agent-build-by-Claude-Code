# Module 13 Checklist — Multiple MCP Servers

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain why connecting a **second** server
      creates **collisions**, and how **namespacing** (`<server>.<tool>`) fixes
      both the collision *and* the routing problem at once.
- [ ] I can separate the two routing layers: **capability routing** (which tool —
      the agent's job) vs **transport routing** (which session — the registry's
      job), and say why keeping them apart matters.
- [ ] My `route()` sends math to `calculator.multiply`, an order id to
      `orders.get_order_status`, a policy question to the **local**
      `document_search`, a weather hint to the optional `weather.forecast`, and an
      ambiguous question to `none`.
- [ ] My `answer()` returns **every** reply in one consistent
      `[source | ok|unavailable] body` format, whether it came from MCP, the local
      tool, a graceful tool error, a down server, or the clarify path — and it
      **never raises**.
- [ ] My `run_demo()` registers `calculator` + `orders` (real) and an optional
      `weather` server that **fails to spawn**, then connects, discovers a
      **6-tool namespaced** table, and prints per-server **health**.
- [ ] `TECHCORP_OFFLINE=true uv run python course/13_multi_server_mcp/starter/multi_agent.py`
      shows `calculator up / orders up / weather DOWN`, computes
      `multiply(125,48)=6000.0`, reports `TC-1234` as `in_transit`, returns
      retrieved policy text for the damaged-product question, and degrades
      cleanly for both `TC-9999` and the weather prompt — **no traceback, no
      crash**.
- [ ] I understand **partial failure**: a **nonessential** server that fails is
      marked down and skipped; an **essential** one aborts `connect_all`. I can
      say which class the orders server would be for an order-support agent, and
      why.
- [ ] I understand **health**: a call into a down server returns a clean
      `is_error=True` result rather than hanging, and `health()` shows me which
      servers are up and how many tools each contributes.
- [ ] **Permissions:** I can explain that registering a server is a permission
      decision — an agent can only route to the servers the host chose to
      `register()`, so `discoverable ≠ permitted` now holds at the *server*
      granularity.
- [ ] **Lifecycle:** I can explain spawn → initialize → discover → call → close,
      and why every server (even a failed one) must be closed, and why all of it
      must run inside the same task / `async with registry:` block.
- [ ] I can explain why `document_search` stays a **local** in-process tool while
      the calculator and orders are **MCP servers** (a boundary you don't need is
      latency and failure surface you don't want).
- [ ] I can articulate the trade-off: **more servers = more capability AND more
      failure surface + latency**; each server is a trust, permission, and
      monitoring decision, not a free win.
- [ ] `uv run pytest course/13_multi_server_mcp -q` passes with `test_my_work.py`
      no longer skipped, and
      `uv run pytest tests/test_mcp_registry.py tests/test_mcp_calculator.py -q`
      passes (the calculator tests confirm I didn't break Module 12's server).
- [ ] (Stretch) I added a real third MCP server and watched it appear as
      `weather.forecast` (7 tools total) with **no change to `route` or
      `answer`** — capability added by one `register()` call.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 13.
```
