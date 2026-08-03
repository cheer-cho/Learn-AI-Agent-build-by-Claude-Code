# Module 19 Checklist — Observability and Evaluation at Scale

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words: why "it seems to work" is not an engineering answer, and what a **trace** buys me that a five-question demo does not.
- [ ] I can define **run**, **step/span**, **inputs/output**, and **metrics**, and map each onto both our `LocalTracer` fields and LangSmith's vocabulary.
- [ ] I can explain why the trace log is **JSONL** (append-only, greppable, one record per line, no parser needed) and why the tracer writes the line **even when the run raises** (a failure is data, not a gap).
- [ ] I can name LangSmith's four core objects — **project, dataset, experiment, feedback** — and say which local artifact each corresponds to.
- [ ] I can state the spec rule and defend it: **LLM-as-judge is never the only validation.** I can give the three reasons — circularity, drift, cost — and explain the `combine_scores` contract (deterministic checks **gate**; the judge only **refines**).
- [ ] I can explain **regression testing** as "treat prompts like code": run the same dataset through old and new, compare per metric *and per example*, because an aggregate can stay flat while specific examples break.
- [ ] I can explain why Lab C **overrides by composition** instead of editing the shared `RAGPipeline` (the shared code is used by Modules 08/09/14/17).
- [ ] `starter/observability_lab.py` has no remaining `TODO` markers.
- [ ] Lab A wrote one JSON line per run to `artifacts/traces/runs.jsonl`, and `scripts/view_traces.py` shows the table (run id, name, route, tokens, latency, error) plus a p50/p95 latency summary.
- [ ] `scripts/view_traces.py --run <id>` expands one run into its ordered steps (router → route node → formatter).
- [ ] Lab B ran the baseline experiment over the Module 09 dataset and printed a per-metric baseline (offline: `hit_rate≈0.84`, `source_accuracy≈0.60`).
- [ ] Lab C dropped the citation rule **by composition**, re-ran, and I saw the regression caught: `source_accuracy` fell ~0.32 and 8 specific examples appeared in the `regressions` list.
- [ ] I can answer the completion question — "How do you know your change improved (or broke) the agent?" — with the comparison table and the named regressed examples, not a feeling.
- [ ] (Optional) With a free `LANGSMITH_API_KEY`, I mirrored the same runs to the LangSmith UI and confirmed the local JSONL write still works with no key.
- [ ] `uv run pytest course/19_observability_and_evaluation -q` passes with `test_my_work.py` no longer skipped.
- [ ] `uv run pytest course/19_observability_and_evaluation tests/test_tracing.py -q` passes (the shared tracing library is intact).
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 19.
