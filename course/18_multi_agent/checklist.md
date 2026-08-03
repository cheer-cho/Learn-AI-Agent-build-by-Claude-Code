# Module 18 Checklist — Multi-Agent Systems

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words: when one agent with
      many tools stops scaling (prompt bloat, tool confusion) and how the
      supervisor pattern addresses it.
- [ ] I can describe each specialist's **focused prompt and small tool set**, and
      why scoping a specialist's retrieval to a category allow-list is what makes
      it a specialist.
- [ ] I can explain **shared vs private state** at a handoff and why the
      supervisor passes only the question, not the whole conversation.
- [ ] I can name the three real costs of multi-agent — **tokens, latency, and
      debugging difficulty** — and say why a multi-agent bug is a
      distributed-systems bug.
- [ ] I can state the **synthesis trade-off**: pass-through (cheap, preserves the
      specialist's cited answer) vs a synthesis LLM call (smoother voice, extra
      call/tokens, risk of dropping a number or citation).
- [ ] `starter/multi_agent_lab.py` has no remaining `TODO` markers.
- [ ] `TECHCORP_OFFLINE=true uv run python course/18_multi_agent/starter/multi_agent_lab.py`
      runs offline end to end and prints the comparison table.
- [ ] My comparison shows the supervisor (with synthesis on) using **more LLM
      calls and more tokens** than the single agent — and I *embrace* that as the
      honest cost of the pattern, not a bug.
- [ ] I read the offline **latency** number with care: I understand it is
      retrieval-dominated against the mock and that the call/token deltas are the
      durable signal.
- [ ] I wrote the comparison report and can point to its per-question source
      columns.
- [ ] I answered **in writing**: "When would you ship the single agent instead?"
      — grounded in my own numbers, not a slogan.
- [ ] `uv run pytest course/18_multi_agent -q` passes with `test_my_work.py` no
      longer skipped.
- [ ] `uv run pytest tests/test_multi_agent.py -q` passes (the agents library).
- [ ] (Optional, stretch) I added a fourth privacy/GDPR specialist and recorded
      the routing confusion it introduced — or the fact that it added cost
      without adding a correct answer.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 18.
