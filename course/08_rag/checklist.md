# Module 08 Checklist — Retrieval-Augmented Generation

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words, the three RAG stages — retrieval, augmentation, generation — and which pipeline function does each.
- [ ] I can explain why RAG supplies evidence at runtime and does **not** modify the underlying model, and one consequence of that (e.g. retrieval quality caps answer quality).
- [ ] `starter/my_rag.py` has no remaining `TODO` markers.
- [ ] `uv run python course/08_rag/starter/my_rag.py` runs offline end to end and prints, for the mini corpus: `hr-dress-code score=0.241` retrieved, the `[source: hr-dress-code]` context block, the grounded answer with `sources: ['hr-dress-code']` and `abstained: False`.
- [ ] `parse_answer` splits a reply into `(answer, sources)`: it strips the `SOURCES:` line off the answer, returns `[]` for `SOURCES: none` / a missing line, handles any case, and de-duplicates while preserving order (`test_parse_answer_*` pass).
- [ ] A fully answerable question is grounded with its correct source, the `SOURCES:` line is split off the answer, and the prompt carries both the rules (`ONLY from the context documents`) and the evidence (`[source: ...]`), ending in `Question: ...`.
- [ ] A partially answerable question cites what exists and passes through the acknowledged gap without inventing the missing part.
- [ ] An unanswerable question (empty retrieval) abstains, returns exactly `ABSTENTION_TEXT`, credits no sources, and makes **zero** LLM calls — I confirmed `llm.calls == []` / `LLM calls: 0`.
- [ ] Conflicting retrieved chunks are both supplied to the prompt and both credited; a multi-chunk question supplies and credits both of its sources.
- [ ] A low-similarity question below `min_score` abstains, with zero LLM calls — I can explain that this is the threshold rejecting weak coincidental matches as evidence.
- [ ] A hallucinated citation (a source id the model was never supplied) is filtered out of `result.sources` — I filter against the retrieved chunks' `doc_id`s, not the model's claimed list.
- [ ] A model-side abstention is detected (`ABSTENTION_TEXT` in the reply) and carries no sources.
- [ ] The final block prints `identical RAGAnswer from both pipelines: True` — my `MyRAGPipeline` is behavior-identical to `techcorp_agent.rag.RAGPipeline`.
- [ ] I can explain why abstention is a feature, not a failure, for an internal policy assistant.
- [ ] `uv run pytest course/08_rag -q` passes with `test_my_work.py` no longer skipped.
- [ ] (Optional) I ran the `min_score` stretch exercise and observed the abstention rate change as I moved the threshold.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 08.
