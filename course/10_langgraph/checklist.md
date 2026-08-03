# Module 10 Checklist — LangGraph Fundamentals

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words: graph, node, edge, conditional edge, entry point, and end state.
- [ ] I can say what **shared state** is and why a node returns a **partial update** rather than the whole state.
- [ ] I understand the `trace` reducer (`Annotated[list, operator.add]`) — why returning `{"trace": [...]}` **appends** instead of overwriting.
- [ ] `starter/graphs.py` has no remaining `TODO` markers.
- [ ] `uv run python course/10_langgraph/starter/graphs.py` runs all four labs offline and prints each trace.
- [ ] **Lab A** produces the final message `Hello, Dana! Welcome to TechCorp.` and status `complete`.
- [ ] **Lab B** passes through `outline → draft → review → finalize` in that order, one LLM call per node, ending in status `finalized`.
- [ ] **Lab C** routes a simple request to `short_explanation` and a complex/policy request to `detailed_policy_analysis`, via a conditional edge (only one branch runs per request).
- [ ] **Lab D** stops at exactly `MAX_ITERATIONS` when the evidence never clears the threshold (`status: max_iterations_reached`) — I can point to the cap check that guarantees the loop is finite.
- [ ] **Lab D** also exits early (before the cap) when the evidence passes the threshold (`status: sufficient_evidence`).
- [ ] Every solution graph records observability: node entered, state fields updated, route selected, iteration number, and final status.
- [ ] I can explain the difference between a **deterministic workflow** (I draw the edges) and an **agentic decision** (the model chooses), and why TechCorp's GDPR review is deliberately the former.
- [ ] I know that **persistence via checkpointers** exists and that the deep dive is Module 15 — I did not need it here.
- [ ] `uv run pytest course/10_langgraph -q` passes with `test_my_work.py` no longer skipped.
- [ ] (Optional stretch) I streamed a graph with `.stream(..., stream_mode="updates")`, and/or saw the `GraphRecursionError` backstop fire when I removed my own cap.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 10.
