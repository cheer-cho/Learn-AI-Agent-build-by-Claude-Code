# Module 09 Checklist — Grounding, Attribution, and Evaluation

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can name the seven ways RAG still fails, and say for each whether it is a retrieval or a generation problem.
- [ ] I can explain the central split in my own words: retrieval evaluation asks "did we fetch the required evidence?", generation evaluation asks "did the answer use it faithfully?" — and I can say which layer a given bad answer points to.
- [ ] `starter/eval_lab.py` has no remaining `TODO` markers.
- [ ] `hit_rate_at_k` returns `1.0` for the vacuous case (empty `expected_sources`), respects the top-`k` slice and rank order, and matches the shared copy in `src/techcorp_agent/evaluation/metrics.py`.
- [ ] `source_accuracy` scores both-empty as `1.0`, missing-citation-when-expected as `0.0`, and invented-citation-when-none-expected as `0.0`.
- [ ] `fact_coverage` is a case-insensitive substring check and I can state its documented blindness: a correct paraphrase scores 0, so the number is a floor, not a ceiling.
- [ ] `abstention_correct` returns `True` only when the two flags agree, and I can explain why both directions of disagreement are failures.
- [ ] `run_and_report` calls `run_evaluation(..., k=4)`, aggregates with `summarize`, writes the report with `write_report`, and returns `(results, summary)`.
- [ ] `uv run pytest course/09_grounding_and_evaluation -q` passes with `test_my_work.py` no longer skipped.
- [ ] `TECHCORP_OFFLINE=true uv run python course/09_grounding_and_evaluation/solution/run_eval.py` produced `artifacts/evaluation_report.md`, and its overall line reads `hit rate@4 88% | source accuracy 28% | fact coverage 28% | abstention accuracy 72%` for 25 examples.
- [ ] The report's **Run context** section names the embedding client (`hash-embedding-384d`) and LLM (`mock-offline`), and I can explain why numbers without that context are misleading.
- [ ] I read the per-category table and identified the weakest real category — `paraphrase` at 60% hit rate — and I can explain why (hash embeddings match words, paraphrases avoid them).
- [ ] I can explain why the generation metrics (source accuracy, fact coverage) are 0% for answerable categories under the mock LLM, and that only the retrieval numbers are meaningful offline.
- [ ] I can state the spec rule: deterministic checks are the required baseline, and a model-based evaluator may be layered on top (Module 19) but must never be the only validation method.
- [ ] `uv run pytest course/09_grounding_and_evaluation tests/test_evaluation.py -q` passes.
- [ ] (Optional, live) I re-ran with a real key and watched the generation metrics start measuring a real model.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 09.
