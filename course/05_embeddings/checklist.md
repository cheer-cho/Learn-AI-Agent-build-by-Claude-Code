# Module 05 — Self-Check & Acceptance Criteria

Work through every box honestly before moving on. If one doesn't hold, revisit the file listed next to it.

## Code (acceptance criteria)

- [ ] `uv run pytest course/05_embeddings -q` passes fully offline — 32 passed, 0 skipped.
- [ ] `starter/embeddings_lab.py` contains no remaining `TODO` markers (that's what un-skips `tests/test_my_work.py`).
- [ ] `uv run python course/05_embeddings/starter/embeddings_lab.py` runs cleanly and prints: the model name and dimension, the vector shape report, the four pair similarities, the ranked documents, and both rankings side by side.
- [ ] My `embed_phrases` calls `client.embed()` once for the whole batch, not once per phrase.
- [ ] My `keyword_score` is pure word-set arithmetic (no embeddings), scores disjoint texts exactly 0.0, and never exceeds 1.0.
- [ ] My `compare_semantic_vs_keyword` returns both rankings best-first, covering every document.
- [ ] I ran the lab with the **real** model at least once (Task 1 header shows `sentence-transformers/all-MiniLM-L6-v2`, not `hash-embedding-384d`) and saw the semantic pairs actually score high.

## Understanding (say each answer out loud — see concepts.md if stuck)

- [ ] I can explain what an embedding is in one sentence (a vector position where the model puts a text so that similar meanings land close together).
- [ ] I can explain **how embeddings permit retrieval by meaning rather than exact wording** — the module's completion criterion — using a concrete pair: "Employee vacation policy" and "Staff time-off guidelines" share no words, yet their vectors sit close (~0.45 cosine), so a query about vacation days finds the time-off document that keyword search scores 0.0.
- [ ] I can name the false positive and false negative of keyword matching from Task 7 and say *why* each happened (shared-but-misleading words; synonymous-but-disjoint words).
- [ ] I can explain what cosine similarity measures (the angle between vectors — direction, not length) and why raw scores are model-relative rather than a universal scale.
- [ ] I can state the embedding-model consistency rule and its cost: vectors from different models are never comparable, so changing models means re-embedding the whole collection.
- [ ] I can explain the difference between the two clients in this repo — `SentenceTransformerClient` (real semantics, local, free, one ~90 MB download) vs `HashEmbeddingClient` (deterministic word overlap, no semantics, used by tests) — and why the tests use the latter.
- [ ] I can explain why the optional 2D plot is only an approximation of the 384-dimensional space, and which number to trust when the plot and cosine disagree.
- [ ] I can name a case where keyword matching *beats* embeddings (exact identifiers like order numbers or error codes) and what that implies for Module 17's hybrid search.

## Looking ahead

- [ ] I understand that Module 06 wraps today's loop — embed, compare, rank — around TechCorp's real document corpus with chunking, top-k, and thresholds, and that Module 07 moves the vectors into a real vector database.

## Done

- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 05.
