# Module 17 — Lab

Upgrade the TechCorp retrieval pipeline one technique at a time, re-measuring after each so every improvement claim is backed by the evaluation dataset. Work in `starter/advanced_rag_lab.py`; run the experiment from `solution/run_experiment.py`.

The golden rule for this whole lab: **measure the baseline, add one technique, re-measure, keep it only if the number moved — and write down the negatives.**

The checkpoints below show the *actual* numbers the reference solution measures on this corpus. Yours should match the offline run closely (hash embeddings are deterministic).

---

## Task 1 — Establish the baseline numbers

Before touching anything, re-read the Module 09 result you're trying to beat. Open `artifacts/evaluation_report.md`:

- overall hit@4: **88%**
- **paraphrase hit@4: 60%** ← the failure this module attacks

Now run the reference experiment offline to see all five configurations at once (this also writes the deliverable):

```bash
TECHCORP_OFFLINE=true uv run python course/17_advanced_rag/solution/run_experiment.py
```

The experiment scores only the categories where *retrieval* is under test — `answerable`, `paraphrase`, `multi_chunk` — because `unanswerable`/`ambiguous` expect no sources (hit@k is vacuously 1.0 there). On those 18 examples the offline baseline scores **hit@4 83%**.

> **Checkpoint 1.** You can state the two numbers you're trying to beat (overall 88%, paraphrase 60%) and you've seen the offline baseline (83% on the scored subset) print.

---

## Task 2 — Add hybrid search, then re-measure

Implement `min_max_normalize` and `hybrid_fuse` in the starter. The idea: vector similarities (~[-1,1]) and BM25 scores (unbounded) live on different scales, so normalize each into [0,1] first, then combine `alpha * vector + (1 - alpha) * bm25`. An id missing from one side scores 0 there.

Read `hybrid_search` in `src/techcorp_agent/rag/advanced.py` to see how your fusion logic is used against a real Chroma store and a `BM25Index`.

Re-measure. On the offline run, hybrid lifts the scored subset from 83% → **94%**, and the paraphrase category from 60% → **80%**:

```
config       hit@4   Δbase
baseline      83%    +0%
+hybrid       94%   +11%   ← BM25 rescues rare-keyword and some paraphrase misses
```

> **Checkpoint 2.** `+hybrid` beats `baseline` on the offline run, and you can name *why* (BM25 finds exact tokens hash vectors dilute). `test_hybrid_beats_baseline_offline` passes.

---

## Task 3 — Add reranking, then re-measure

Implement `overlap_rerank`: score each candidate by the fraction of distinct query tokens it contains, sort best-first, keep top_k. This is the deterministic offline stand-in for the real `CrossEncoderReranker` (read that class too — note the bi-encoder vs cross-encoder distinction from concepts §3).

Reranking works on a *shortlist*: the pipeline fetches a wider pool (top-10), the reranker trims it back to top-4 by precision. Re-measure:

```
config       hit@4   Δbase
+rerank      100%   +17%   ← reorders the right chunk into the top-4; paraphrase 60% → 100%
```

On the offline corpus, reranking pushes the scored subset to a perfect **100%**. That's a precision fix: the right chunks were being retrieved into the pool but ranked too low; the reranker floats them up.

> **Checkpoint 3.** `+rerank` reaches 100% offline, and you can explain that a reranker only *reorders* what retrieval fetched — it can't rescue a missing chunk.

---

## Task 4 — Add query rewriting / multi-query, then re-measure

Implement `parse_rewrites`: keep the original question first, then append up to `n` deduped rewrites (drop any that case-insensitively equal the original or an earlier pick). Read `rewrite_query` and `retrieve_multi_query` in the shared library — note that multi-query fuses with **RRF**, not the weighted sum (concepts §2 explains why).

Re-measure. Here is where you meet a **negative result** and must report it honestly:

```
config       hit@4   Δbase
+rewrite      78%    -6%   ← multi-query HURT on this corpus
```

Why did it hurt? Offline, the rewrites are scripted and deliberately weak (a mock LLM can't invent the corpus's vocabulary). Weak rewrites retrieve off-target chunks that dilute a perfectly good original query and push the right chunk out of the top-4. **This is the point of the lab, not a bug.** A technique that doesn't help is a finding.

> **Checkpoint 4.** You observed `+rewrite` *lower* hit@4 offline and can explain the mechanism (weak rewrites inject noise). You did not "fix" it by hiding the number.

---

## Task 5 — Produce the comparison table and write three honest sentences

Run the full experiment once more, this time **with real embeddings** for the headline table (downloads the sentence-transformers and cross-encoder models once — free, local):

```bash
uv run python course/17_advanced_rag/solution/run_experiment.py
```

This regenerates `artifacts/retrieval_improvement_report.md` with two runs. The measured headline (sentence-transformers) tells the anti-hype story:

```
config       hit@4   Δbase     ms/q
baseline     100%    +0%     8.2     ← naive RAG already aces this corpus
+hybrid      100%    +0%     4.6
+rerank      100%    +0%    31.2     ← 4× the latency, zero gain
+rewrite      89%   -11%    13.8     ← still hurts, even with a real reranker downstream
all          100%    +0%    38.0
```

Now write **three sentences of honest conclusions** (put them in your own notes; the generated report already contains a data-driven version). They should say something like:

1. On this small, clean corpus with real embeddings, naive top-k already scores 100% — the advanced techniques add latency for no measurable gain.
2. The techniques *do* earn their keep on the weaker hash-embedding retrieval, where hybrid (+11%) and reranking (+17%, reaching 100%) recover real ground on paraphrase questions.
3. Multi-query rewriting hurt on *both* runs here (a genuine negative result), because weak rewrites dilute a good original — a reminder to measure before shipping and to keep only what moves the number.

> **Checkpoint 5.** `artifacts/retrieval_improvement_report.md` exists with both runs, a per-config table (hit@4, latency, complexity), a per-category breakdown, and honest findings — including the negatives. You can articulate when you'd choose each technique and when naive RAG is enough.

---

## Debugging hints

- **"BM25Okapi rejects an empty corpus."** The `BM25Index` guards against this; if you hit it, you're building the index before adding chunks. Build it from the same chunk list you indexed in Chroma.
- **Hybrid returns weird orderings.** Check your normalization: if every score is equal (one candidate, or all tied), the range is zero — return 1.0 for each, don't divide by zero.
- **A collection-mismatch error from Chroma.** You queried a store indexed with a different embedding model. The experiment uses a throwaway temp directory per run to avoid exactly this; don't point it at `.chroma/`.
- **Multi-query seems to do nothing offline.** The scripted mock returns fixed rewrites; that's intentional. Its job is to prove the *plumbing* dedups and fuses, not to produce good rewrites. The real quality comes from the live LLM.
- **Live run is slow.** The first live run downloads two models (~80 MB each). Subsequent runs are cached. Use `TECHCORP_OFFLINE=true` for the fast, reproducible loop while iterating.

## Stretch — parent-document retrieval

Implement the concept from §5: index small chunks for precise matching, but when a chunk is retrieved, return its whole *document* (all chunks sharing its `doc_id`, in `index` order) as the context handed to the generator. Measure whether the fuller context changes `fact_coverage` (a Module 09 generation metric) even when hit@4 is unchanged — retrieval precision and answer completeness are different axes.
