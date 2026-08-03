# Module 07 — Self-Check & Acceptance Criteria

Work through every box honestly after finishing lab.md (both Lab A and Lab B). Each box is checkable from the repository root; the code boxes run offline (`TECHCORP_OFFLINE=true`), with no API key. If a box doesn't hold, revisit the file listed next to it.

## Lab A — the chunking experiment (acceptance criteria)

- [ ] `uv run pytest course/07_vector_database -q` passes with **no skips** — `test_my_work.py` is running against my starter code and is green.
- [ ] `starter/chunking_experiment.py` contains no remaining `TODO` markers (that's what un-skips `tests/test_my_work.py`).
- [ ] `duplicate_rate` builds a **set** of 8-word shingles per chunk (within-chunk repeats don't count), returns the fraction seen in more than one chunk, and returns `0.0` for empty or too-short input.
- [ ] `run_config` chunks with `chunk_document(strategy=..., chunk_size=..., overlap=...)`, indexes into a throwaway `VectorStore` collection, calls `reset()` before and after, and returns all twelve metric keys (`name`, `strategy`, `chunk_size`, `overlap`, `chunk_count`, `avg_chunk_chars`, `hit_rate`, `duplicate_rate`, `failures`, `question_count`, `top_k`, `embedding_model`).
- [ ] A **hit** is scored as an `expected_sources` id appearing among the retrieved chunks' `doc_id`s within `top_k=4`; every miss is recorded as a failure dict with `id`, `question`, `expected_sources`, `retrieved_doc_ids`.
- [ ] `uv run python course/07_vector_database/solution/run_experiment.py` prints the summary table for all three configs and writes `artifacts/chunking_report.md`.
- [ ] `artifacts/chunking_report.md` opens with a heading, names the embedding client and the "word overlap" caveat, contains the comparison table with all three config names, and lists per-config failure cases.
- [ ] I can read the deterministic structural numbers off my report: smaller chunks ⇒ more chunks (`small-fixed` ~155 vs `paragraph` ~41), and `medium-fixed`'s 100/800 overlap duplicates ~12% of shingles while `paragraph` duplicates ~0%.

## Lab B — the ChromaDB tour (acceptance criteria)

- [ ] I created a persistent collection with `VectorStore(embeddings, persist_dir=..., collection_name=...)`, added chunks (paragraph config reports 41), and queried it semantically with results sorted best-first.
- [ ] I ran a `category`-filtered query and confirmed every result is in that category (e.g. `privacy`) — a filter is a guarantee, not a tendency.
- [ ] I rebuilt the collection with `store.reset()` (never `rm -rf` the persist dir), confirmed `count() == 0`, and re-added the chunks.
- [ ] I proved persistence by reopening the same `persist_dir` + `collection_name` in a **separate process** and seeing the count survive.

## Understanding (say each answer out loud — see concepts.md if stuck)

- [ ] I can name the four things Module 06's in-memory list can't do that a vector store handles (persistence, scale/ANN, metadata queries, lifecycle).
- [ ] I can explain the cosine **distance** vs similarity convention: Chroma returns distance (lower = closer); the wrapper converts with `1 - distance` so higher = closer, and I know why applying a `min_score` to raw distances would silently keep the worst results.
- [ ] I can state the embedding-model compatibility rule and describe the silent failure the collection's `embedding_model` guard prevents.
- [ ] I can explain why there is **no universal best chunk size**, and what small vs large chunks trade (sharpness/context/prompt tokens), citing my own report's numbers.
- [ ] I can explain what chunk overlap buys (insurance against boundary cuts) and what it costs (duplicate content), and why paragraph splitting needs little or no overlap.
- [ ] I can name the three changes that force a re-index (documents, chunking config, embedding model) and why `reset()` is the safe rebuild (it touches only this collection).

## Wrap up

- [ ] (Optional stretch) I added a fourth configuration, re-ran with the real model, and justified in one sentence which config I'd ship for a RAG prompt.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 07.
