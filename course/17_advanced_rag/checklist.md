# Module 17 Checklist — Advanced RAG

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words: why BM25 and dense vectors fail *differently* (complementary errors), and why fusing them helps.
- [ ] I can state the baseline I'm trying to beat from Module 09: overall hit@4 **88%**, paraphrase hit@4 **60%**.
- [ ] I can explain the bi-encoder vs cross-encoder distinction and why a cross-encoder reranks a shortlist instead of replacing retrieval.
- [ ] I can explain why a reranker fixes *ranking* (precision) but not *coverage* (recall) — it cannot rescue a chunk retrieval never fetched.
- [ ] I can explain query rewriting, multi-query expansion, and query decomposition, and why they are the most expensive stage per query.
- [ ] I can explain parent-document retrieval as a concept: search small chunks, return the larger parent context.
- [ ] `starter/advanced_rag_lab.py` has no remaining `TODO` markers.
- [ ] `min_max_normalize` scales to [0,1] and returns 1.0 for every id when all scores are equal (no divide-by-zero).
- [ ] `hybrid_fuse` unions ids from both sides, weights by `alpha`, and treats a missing id as 0 on that side.
- [ ] `overlap_rerank` orders by query-token overlap fraction, trims to top_k, and preserves input order for an empty query.
- [ ] `parse_rewrites` keeps the original first and dedups rewrites case-insensitively.
- [ ] I ran the experiment offline and observed the measured deltas: `+hybrid` +11%, `+rerank` +17% (to 100%), and `+rewrite` **−6%** — a real negative result I did not hide.
- [ ] I ran the experiment once with real sentence-transformers and saw the anti-hype result: the naive baseline already scores 100%, so the advanced stages add latency for no gain on this corpus.
- [ ] `artifacts/retrieval_improvement_report.md` exists with a per-config table (hit@4, latency ms/query, complexity), a per-category breakdown, "when is it worth it" guidance, and honest findings including negatives.
- [ ] I wrote three sentences of honest conclusions and can say, for each technique, when I would and would not adopt it — and when naive RAG is enough.
- [ ] `uv run pytest course/17_advanced_rag -q` passes with `test_my_work.py` no longer skipped.
- [ ] `uv run pytest course/17_advanced_rag tests/test_advanced_rag.py -q` passes (the shared library is intact).
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 17.
