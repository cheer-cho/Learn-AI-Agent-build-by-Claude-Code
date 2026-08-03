# Module 11 Checklist — Tools and Intelligent Routing

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words: what a tool is (name, description, input schema, output), and why the **description** drives routing quality more than the code.
- [ ] I can state the difference between LLM routing and deterministic keyword routing, and why `route_question` uses the keyword router as a fallback.
- [ ] `starter/agent.py` has no remaining `TODO` markers.
- [ ] `TECHCORP_OFFLINE=true uv run python course/11_tools_and_routing/starter/agent.py` runs offline end to end and routes: math → `[calculator] 6000`, `TC-1234` → `in_transit`, the damaged-return question → `document_search`, `TC-9999` → a graceful "could not help", and the ambiguous question → the LLM.
- [ ] My `answer` loop never wraps a tool body in `try/except` — it relies on `run_tool` to return a `ToolResult`, and it branches only on `result.ok`.
- [ ] I observed all six failure modes and none printed a traceback:
  - [ ] **Ambiguous query** → routed to `none`, answered by the LLM with a clarifying question.
  - [ ] **Missing required argument** → `order_lookup` with no id returns a failure naming `order_id`.
  - [ ] **Tool timeout** → a slow tool returns a "timed out after…" failure.
  - [ ] **Tool returns no data** → unknown order / empty index returns a helpful `ok=False`.
  - [ ] **Tool raises** → the exception is caught at the tool boundary and returned as a failure.
  - [ ] **Wrong-tool selection** → an invalid LLM reply falls back to `keyword_route` and recovers.
- [ ] I can explain why every tool in this module is **read-only**, and where authentication, authorization, and human approval will go when write-capable tools arrive (Module 16).
- [ ] `uv run pytest course/11_tools_and_routing -q` passes with `test_my_work.py` no longer skipped.
- [ ] `uv run pytest tests/test_tools.py -q` passes (the shared tools the later modules reuse).
- [ ] I can name at least one question `keyword_route` legitimately cannot decide from surface text, and why that is the LLM router's job.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 11.
