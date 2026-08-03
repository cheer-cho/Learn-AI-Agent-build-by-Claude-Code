# Module 22 Checklist — Hero Capstone: TechCorp Knowledge Agent v2

This is the Level 5 finale, so the list below is the spec's **full capstone
acceptance criteria** restated as things *you* can check. Be honest — this is the
project you will demo in an interview.

## Integration and reuse

- [ ] Setup works from a clean environment: `uv sync`, then
      `TECHCORP_OFFLINE=true uv run python course/22_hero_capstone/solution/capstone_v2.py`
      runs with no API key and no network.
- [ ] I can name what v2 **reuses** — the multi-agent supervisor (18), advanced
      retrieval (17), durable memory (15), streaming + approval (16), MCP + fallback
      (13–14), safety (20), tracing (19), and the FastAPI patterns (21) — and I can
      point at the exact package each comes from. v2 reimplements none of them.
- [ ] My `starter/capstone_v2.py` has **no `TODO` markers left**, and
      `uv run pytest course/22_hero_capstone -q` passes with `test_my_work.py` no
      longer skipped.

## All Module 14 acceptance criteria still pass

- [ ] International-remote question routes to a knowledge specialist and cites
      `hr-international-remote`.
- [ ] Jeans/dress-code question retrieves and cites `hr-dress-code`.
- [ ] `17.5% of 8,400` returns **1470** and is **not** attributed to documents.
- [ ] A known order (TC-1234) returns its status; an unknown order (TC-9999)
      returns a safe message, never a crash.
- [ ] The "working from the Moon" question **abstains** instead of inventing
      policy.

## The v2 upgrades

- [ ] **Memory persists across restarts.** A follow-up resolves against an earlier
      turn, and the conversation survives a **new graph built on the same sqlite
      file** (`test_multi_turn_memory_survives_new_graph_on_same_sqlite`).
- [ ] **The supervisor routes to the correct specialist** — a support-domain
      question reaches the support specialist, a policy-domain question the policy
      specialist.
- [ ] **Advanced retrieval** (hybrid + rerank) is on by default for the knowledge
      routes, and I can explain the Module 17 result that justifies it (paraphrase
      60% → 100% offline) and why it may be a wash live.
- [ ] **Streaming works in the CLI and over HTTP.** `--stream` prints the event
      feed; the FastAPI `/chat/stream` emits the same events as SSE.
- [ ] **The approval interrupt works end to end.** The ticket write pauses before
      creating anything, creates a `TCK-XXXX` on approve, and creates nothing on
      reject.
- [ ] **The injection defense lab passes.** A direct prompt-injection question is
      blocked at the boundary; I can show the before (detection) and after (refusal).
- [ ] **Budget enforcement refuses** an over-budget session before any model call.
- [ ] **Tracing captures the run** — a traced invoke writes a non-empty run log.
- [ ] **MCP-unavailable falls back** without crashing — with `--no-mcp` (or a
      failed spawn) math and order questions still answer via local tools.

## The service and delivery

- [ ] The service starts via a documented command, with **and** without Docker
      (`uv run uvicorn techcorp_agent.capstone_v2.app_service:app --reload`), and
      `/health` / `/ready` / `/chat` / `/chat/stream` respond.
- [ ] I did **not** break the existing service — `uv run pytest tests/test_api.py -q`
      still passes green.
- [ ] CI configuration exists and the **offline suite passes locally**:
      `uv run pytest course/22_hero_capstone tests/test_capstone_v2.py -q`, and the
      whole-repo `uv run pytest -q` is unbroken.

## The evaluation report

- [ ] `TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone_v2.report`
      generates `artifacts/capstone_v2_report.md`, and I can read it honestly:
      routing is deterministic (keyword fallback), retrieval uses the advanced
      config with each example traced, the integration smoke checks all pass, and
      only retrieval-side numbers are meaningful with the mock LLM.

## Career deliverables (authored separately, but I can defend them)

- [ ] The four career documents exist alongside this module and reference real
      code: `ARCHITECTURE.md`, `DEMO_SCRIPT.md`, `PORTFOLIO_README.md`,
      `INTERVIEW_PREP.md`.
- [ ] I can defend **every integration trade-off** out loud: advanced RAG on/off,
      the multi-agent routing cost, memory footprint + summarization, approval
      friction, and safety overhead vs false positives.

## Milestone

- [ ] v2 is a production rollout I could demo to an interviewer today, and I can
      describe — in one paragraph — how twenty-one modules of components integrate
      into this one agent.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 22 — you've
      reached HERO. 🎓
