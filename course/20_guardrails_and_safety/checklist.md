# Module 20 Checklist — Guardrails, Safety, and Cost Control

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words, the **trust
      boundary**: why retrieved documents and tool results are untrusted input.
- [ ] I can describe the difference between **direct** and **indirect** prompt
      injection, and why RAG systems are especially exposed to the indirect kind.
- [ ] I ran the reference before/after and saw the **unprotected** path leak
      order data and the **protected** path block the same hijacked output:
      `TECHCORP_OFFLINE=true uv run python course/20_guardrails_and_safety/solution/safety_lab.py`
- [ ] `starter/safety_lab.py` has no remaining `TODO` markers.
- [ ] Lab A: `detect_injection` flags the planted payload, `sanitize_context` +
      `harden_system_prompt` fence it, and `validate_answer` blocks the leaking
      answer (protected path serves the abstention instead).
- [ ] I can explain the **modeling note**: why the offline mock is scripted with
      the hijacked completion, and what a real LLM would do with the raw payload.
- [ ] Lab B: output validation blocks a **missing-citation** answer and an
      **invented-citation** answer, and passes a clean abstention.
- [ ] Lab C: the `SessionBudget` **warns** at the soft limit and **refuses** a
      further call at the hard limit, with a clear user-facing message — and no
      billable call is made after the hard limit (`guarded_complete` fails closed).
- [ ] I can name the four cost bounds — budget, token cap, timeout, fallback —
      and which one `guarded_complete` enforces for each.
- [ ] I can explain why `detect_injection` is documented as a heuristic starter
      set, and why detection is only one layer of a defense-in-depth stack.
- [ ] I can state at least two of the module's misconceptions and why they are
      wrong (e.g. "the system prompt always wins", "my tools are safe by default").
- [ ] `uv run pytest course/20_guardrails_and_safety -q` passes with
      `test_my_work.py` no longer skipped.
- [ ] `uv run pytest tests/test_safety.py -q` (the toolkit's unit tests) passes.
- [ ] (Stretch) I added a new injection pattern and a detector test for it —
      proving it fires on the new phrasing and does not false-positive on a clean
      document.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 20.
