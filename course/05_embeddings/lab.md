# Lab 05 — Turn Meaning into Numbers

## Scenario

Level 2 begins. TechCorp's help desk drowns in tickets that the knowledge base already answers — because employees search for "vacation days" while the document is titled "Staff time-off guidelines", and search for "forgot my password" while the page is called "Account recovery". Your tech lead has approved building semantic search (Module 06), but first she wants proof that the core idea works: that a program can rank documents by *meaning*. Your task this week: build the measurement harness — embed phrases, compute similarities, rank documents against a query, and document exactly where keyword matching fails and semantic matching doesn't. Modules 06–08 and the capstone will be built directly on top of what you write here.

## Learning objectives

By the end of this lab you can:

1. Load an embedding model and read off its name and dimension.
2. Embed a batch of phrases and describe the shape of what comes back.
3. Compute and interpret cosine similarity between texts.
4. Rank documents against a query by meaning with `rank_by_similarity`.
5. Demonstrate — with concrete examples — one false positive and one false negative of keyword matching.

## Setup

Confirm you're ready:

```bash
uv run python -c "import techcorp_agent; print('ok')"
```

Your working file is `starter/embeddings_lab.py`. Run it any time — it always runs, and tells you which tasks remain:

```bash
uv run python course/05_embeddings/starter/embeddings_lab.py
```

The first run downloads the embedding model once (~90 MB, free); after that everything is local and instant. No API key is ever needed. If the download is impossible where you are, the provided `load_client()` falls back to the offline `HashEmbeddingClient` and prints a notice — the lab still runs, but similarity scores become word-overlap only (concepts.md explains why that matters). All *tests* are offline either way.

---

## Task 1 — Load an embedding client

No code to write — this one is a reading task. Open `starter/embeddings_lab.py` and read `load_client()` (provided). Note the three-step story: `get_embedding_client()` picks the configured client, the `client.embed(["warm-up"])` call forces the lazy model download *now* rather than mid-lab, and the `except` clause falls back to `HashEmbeddingClient` so the file runs anywhere.

**Checkpoint 1.** Run the starter. The header should show the real model:

```text
Task 1 — load an embedding client
  model: sentence-transformers/all-MiniLM-L6-v2
  dimension: 384
```

If you see `model: hash-embedding-384d` instead, the fallback kicked in (no network, or `TECHCORP_OFFLINE=true` is set). You can still do every task — but your similarity numbers will differ from the checkpoints below, and the Task 6/7 contrast won't show. Re-run online when you can.

## Task 2 — Embed several phrases

Implement `embed_phrases(client, phrases)`.

- Call `client.embed(...)` **once** with the whole list — embedding models batch efficiently; per-item calls are an anti-pattern you'd pay for in Module 07.
- Return a dict mapping each phrase to its vector, same order. (`zip` plus `dict` is all you need. That dict shape is exactly what `rank_by_similarity` takes as candidates — deliberate.)

The `PHRASES` list is provided: the two same-meaning pairs from concepts.md plus one unrelated phrase.

## Task 3 — Inspect the vectors

No new code — the starter's Task 2/3 step reports on what your `embed_phrases` returned.

**Checkpoint 2/3.** With the real model:

```text
Task 2/3 — embed phrases and inspect shape
  5 phrases -> 5 vectors of 384 floats each
  'Employee vacation policy' starts with [+0.0114, +0.0585, +0.0753, -0.0320, +0.0050, ...]
```

Things to actually look at: every vector has the same length (the model's `dimension`, 384) no matter how long the text is; the numbers are small, positive and negative, and individually meaningless. A three-word phrase and a whole paragraph both become exactly 384 floats.

## Task 4 — Cosine similarity between pairs

Implement `similarity_matrix(vectors)`.

- Entry `[i][j]` is `cosine_similarity(vectors[i], vectors[j])` — the helper is already imported from `techcorp_agent.similarity`.
- A nested list comprehension does it in one line. N vectors in, N×N matrix out.

**Checkpoint 4.** With the real model, the starter prints the pair scores:

```text
Task 4 — cosine similarity between pairs
  +0.446  'Employee vacation policy' vs 'Staff time-off guidelines'
  +0.518  'Forgot my password' vs 'Account recovery'
  +0.039  'Employee vacation policy' vs 'Forgot my password'
  +0.073  'Staff time-off guidelines' vs 'TechCorp quarterly revenue report'
  (self-check: matrix diagonal is all 1.0, matrix is symmetric)
```

Stop and read those four numbers. The two same-meaning pairs score ~0.45–0.52 with **zero shared words**; the two different-meaning pairs score ~0.04–0.07. Wording didn't matter; meaning did. Also verify the two matrix properties the self-check line asserts — a vector compared with itself is 1.0, and `[i][j] == [j][i]` — they're your cheapest pipeline sanity checks and the tests check them too.

## Task 5 — Rank documents against a query

No new code — this step uses `rank_by_similarity` from `techcorp_agent.similarity` with your `embed_phrases` output (look at `show_ranking()` in the starter to see how little glue it takes). The provided `QUERY` and `DOCUMENTS` are a TechCorp help-desk question and five candidate documents.

**Checkpoint 5.** With the real model:

```text
Task 5 — rank documents against: 'How many vacation days do employees get each year?'
  +0.731  Employee vacation policy: full-time employees receive 20 paid vacation days per year.
  +0.499  Staff time-off guidelines: permanent staff accrue four weeks of paid annual leave.
  +0.396  Vacation photo contest: employees who post vacation photos get extra raffle entries.
  +0.254  TechCorp quarterly revenue grew four percent year over year.
  -0.030  Forgot my password: use the account recovery page to reset your login credentials.
```

The ranking reads like a human sorted it: the direct answer first, the rephrased answer second, the topically-adjacent distractor third, then noise. This one function call *is* the heart of semantic search — Module 06 adds real documents, chunking, and thresholds around it.

## Task 6 — Semantic ranking vs keyword ranking

Two functions this time.

First implement `keyword_score(query, text)` — the naive baseline embeddings will be judged against:

- Tokenize both strings with the provided `_WORD_RE.findall(s.lower())` and build **sets** of words.
- Return the fraction of the query's words that also appear in the text: `|query ∩ text| / |query|`.
- Disjoint sets — or an empty query — score exactly `0.0`.

Then implement `compare_semantic_vs_keyword(client, query, documents)`:

- `"semantic"`: embed the query (`client.embed([query])[0]`), reuse `embed_phrases` for the documents, rank with `rank_by_similarity`.
- `"keyword"`: score every document with `keyword_score`, sort best-first (`sorted(..., key=..., reverse=True)`).
- Return both in one dict: `{"semantic": [...], "keyword": [...]}` — each a list of `(document, score)` tuples, best first.

**Checkpoint 6.** The starter now prints both rankings for the same query. They *disagree*, and the disagreement is the entire point of this module.

## Task 7 — Find keyword matching's two mistakes

No new code — analysis. Compare the two rankings from Checkpoint 6 and write down (really — say it out loud or write it in a comment):

1. **One false positive of keyword matching**: a document that keyword ranks *highly* but that does not answer the query. What words fooled it?
2. **One false negative of keyword matching**: a document that *does* answer the query but keyword ranks at the bottom. Why does it score zero?

Then check your answer against the solution's output — run `uv run python course/05_embeddings/solution/embeddings_lab.py`, whose Task 6/7 table flags both mistakes explicitly. (With the real model: keyword puts the *photo contest* doc at #2 on the strength of the words "vacation"/"employees"/"get" — false positive, semantic rank #3; and it scores the *time-off guidelines* doc 0.00 because "four weeks of paid annual leave" shares not one word with the query — false negative, semantic rank #2 at +0.499.) These two failure modes are precisely what "retrieval by meaning rather than exact wording" fixes, and being able to *say that with an example* is this module's completion criterion.

## Optional task — a 2D picture of the space

The provided `try_plot_2d()` projects your 5 phrase vectors from 384 dimensions down to 2 with PCA and saves a scatter plot to `artifacts/m05_embeddings_2d.png`. It runs **only if** `matplotlib` and `scikit-learn` are both already installed; otherwise it prints a friendly skip message. **Do not install anything for this** — the course deliberately doesn't depend on plotting libraries, and skipping this task loses you nothing.

If it does run for you, expect the two same-meaning pairs to appear as two loose clusters, with the revenue phrase off on its own. But keep concepts.md's warning in mind: **a 2D plot of a 384-dimensional space is only an approximation.** PCA keeps the two directions with the most spread and throws away the other 382 — distances in the picture are *hints*, not measurements. When the plot and `cosine_similarity` disagree, the cosine on the full vectors is the truth.

## Final check

```bash
uv run pytest course/05_embeddings/tests/test_my_work.py -q
```

All tests should pass (they stop auto-skipping once no `TODO` remains in `starter/embeddings_lab.py`). Then run the whole module suite:

```bash
uv run pytest course/05_embeddings -q
```

Expected: `32 passed` (16 for the reference solution, 16 for yours) — fully offline, no model download needed.

---

## Debugging hints

- **First run hangs or fails on download** — the model is ~90 MB from Hugging Face on first use. Slow is normal once; a hard failure trips the fallback and prints `NOTE: falling back to HashEmbeddingClient`. Fix your network and re-run; the download resumes/caches.
- **All my similarity scores look like word-counting (synonym pairs score ~0.0)** — you're on the hash client. Check the Task 1 header line; unset `TECHCORP_OFFLINE` and make sure the model can download.
- **Tests still skipping after you finished** — the skip triggers on the literal string `TODO` anywhere in `starter/*.py`. Delete the marker comments, not just the `raise` lines.
- **`ValueError: Vector dimensions differ`** — you compared vectors from two different clients (e.g. one embed before the fallback fired, one after). Embed everything with the *same* client object in one run. This is the one-index-one-model rule biting you at lab scale.
- **`test_maps_every_phrase_to_a_vector` fails on key order** — build the dict from the phrases in their given order (`dict(zip(phrases, vectors, strict=True))`); don't sort or set-ify.
- **`test_all_query_words_present_scores_one` fails** — divide by the number of *query* words, not text words or the union, and compare **sets**, not lists (repeated words must not double-count).
- **`test_disjoint_word_sets_score_zero` fails with a tiny nonzero score** — you're using cosine on hash vectors for the keyword score. `keyword_score` must be pure set arithmetic on words; no embeddings involved.
- **`test_both_rankings_sorted_best_first` fails** — `rank_by_similarity` already sorts the semantic list; the keyword list you sort yourself, and it needs `reverse=True` (biggest score first).
- **Scores differ from the checkpoints in the 3rd decimal** — fine. Different `sentence-transformers`/`torch` versions can wiggle the numbers slightly; the *ordering* is what matters.

## Stretch exercise

**Break the embedding model.** Semantic similarity has failure modes too, and finding them yourself is the best inoculation against treating it as magic. Extend `main()` (or a scratch script) to test:

1. **Negation**: `cosine_similarity` between "Refunds are allowed after 30 days" and "Refunds are not allowed after 30 days". Prediction before you run it?
2. **Exact identifiers**: rank the query `"order ORD-7841 status"` against documents mentioning `ORD-7841`, `ORD-7814`, and `ORD-9999`. Does the model reliably distinguish them, and would `keyword_score`?
3. Write a two-sentence recommendation: when should TechCorp's future search combine keyword and semantic signals rather than use semantic alone? (You'll implement exactly that as hybrid search in Module 17.)

When everything passes, finish with [checklist.md](checklist.md).
