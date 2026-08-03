# Module 06 — Self-Check & Acceptance Criteria

Work through every box honestly after finishing lab.md. Each one is checkable from the repository root; the code boxes run offline, with no API key. If a box doesn't hold, revisit the file listed next to it.

## Code (acceptance criteria)

- [ ] `uv run pytest course/06_semantic_search -q` passes with **no skips** — `test_my_work.py` is running against my starter code and is green (offline, deterministic hash client).
- [ ] `starter/search_engine.py` contains no remaining `TODO` markers (that's what un-skips `tests/test_my_work.py`).
- [ ] `uv run python course/06_semantic_search/starter/search_engine.py` runs cleanly and prints the model line, the `13 documents → ~67 chunks` corpus line, and, for each of the four `TEST_QUERIES`, both a `semantic:` and a `keyword :` result block.
- [ ] `SearchEngine.index` chunks with `chunk_document` and embeds **all chunk texts in one batch call** (`self.embedding_client.embed([...])`), not one call per chunk, and returns the number of chunks added.
- [ ] `self.chunks` and `self.vectors` stay aligned — position i of one corresponds to position i of the other (Checkpoint A: `13` documents → roughly `60`–`75` chunks; `13` chunks total means I embedded whole documents, not chunks).
- [ ] `SearchEngine.search` embeds the query with the **same** client, scores every chunk with `cosine_similarity`, wraps each as a `RetrievedChunk`, sorts descending, and returns the first `top_k`.
- [ ] `min_score` drops results below the threshold **before** truncating, and returning an **empty list is possible** — `search(RECOVER_QUERY, min_score=0.45)` with real embeddings correctly returns nothing.
- [ ] `keyword_search` scores each chunk as `len(query_words & chunk_words) / len(query_words)` using `tokenize()`, skips zero-overlap chunks, and returns an empty list for an all-stopwords query.
- [ ] I ran the lab with the **real** model at least once (the model line reads `sentence-transformers/all-MiniLM-L6-v2`, not `hash-embedding-384d`) and saw "Can I wear jeans at the office?" put **Dress Code Policy** on top near `0.67` (Checkpoint B/C).

## Understanding (say each answer out loud — see concepts.md if stuck)

- [ ] I can describe the two phases of the pipeline and what happens once vs per query (index: load → chunk → embed → store; search: embed query → cosine-rank → top-k → threshold).
- [ ] I can explain why we embed **chunks, not whole documents**, and what each `Chunk`'s metadata (`doc_id`, `doc_title`, `category`, `index`) is later used for.
- [ ] I can explain what `top_k` trades off (too small = the right answer can be absent; too large = the right chunk buried under distractors) and what a `min_score` threshold protects against (top-k always returns k results, even when nothing is relevant).
- [ ] I can define precision and recall and say which knob (higher k, higher threshold) raises which and at what cost.
- [ ] I can name, with evidence from my own run, when semantic search beats keyword search ("Can I work from home?" — a paraphrase, where keyword search returns a confident three-way tie at 1.000) and when keyword search is genuinely fine (the corpus contains the literal words "jeans" and "broken").
- [ ] I can explain why "How do I recover my account?" is answerable by **neither** method — no account-recovery document exists — and what the honest system response is (an empty result under a threshold).
- [ ] I can state the same-model rule: query and corpus must be embedded by the identical client, or the cosine scores are meaningless.

## Wrap up

- [ ] (Optional stretch) I added the `category` filter to `search` and watched "How long are records kept?" commit to one topic when scoped to `privacy` vs `employee_handbook`.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 06.
