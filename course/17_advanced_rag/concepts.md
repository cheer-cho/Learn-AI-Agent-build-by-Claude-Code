# Module 17 — Concepts

Read this before the lab. It explains *why* each retrieval upgrade exists, grounded in the failures you already measured in Module 09, and — just as important — when you should not bother.

---

## 1. Naive top-k retrieval, and where it actually fails

The Module 08 pipeline does one thing to find evidence: embed the question, embed every chunk, return the `k` chunks with the closest vectors. That is *naive top-k retrieval*, and for a lot of questions it is completely fine.

But Module 09 measured it instead of trusting it, and `artifacts/evaluation_report.md` records the weak spots. With the deterministic hash embeddings:

| category | hit@4 |
|---|---:|
| overall | 88% |
| answerable | 90% |
| **paraphrase** | **60%** |
| multi_chunk | 100% |

The **paraphrase 60%** is the headline failure and the whole reason this module exists. Look at what the paraphrase questions do (`data/evaluation/eval_dataset.json`):

- "Am I allowed to wear **denim** at headquarters?" — the document says **jeans**.
- "Where can I find the staff **time-off guidelines**?" — the document is titled **Vacation and Time Off Policy** but the question's phrasing shares few words with the body.
- "Can I sync my work files to my own **Dropbox**?" — the policy talks about **personal cloud storage**.

Hash embeddings match on word overlap, so "denim" and "jeans" score as unrelated and retrieval misses. That is a *retrieval* failure, not a generation failure — the model never even sees the right chunk, so no amount of prompt engineering downstream can fix it.

The classic taxonomy of naive-RAG failure modes:

1. **Vocabulary mismatch** — the query and the answer use different words for the same thing (the paraphrase failure above).
2. **Rare-keyword dilution** — a query pivots on a rare token ("XR-4000", an error code) that dense embeddings underweight because it is drowned out by common words.
3. **Ranking, not coverage** — the right chunk *is* in the top-20 but not the top-4 the generator is given, so it is effectively invisible.
4. **Compound questions** — one question needs evidence from two documents ("can support refund me, or does someone else sign off?"), and a single query pulls chunks about one half only.

Each advanced technique targets a specific failure. Reach for the one that matches the failure you *measured*, not the one that sounds most impressive.

---

## 2. Hybrid search: BM25 and vectors fail differently

**BM25** is a decades-old lexical ranking function. It scores a document by term frequency × inverse document frequency: a rare query word that appears in a chunk drives the score up hard, a common one barely moves it. BM25 is exact-match: it finds "XR-4000" instantly and is *blind to synonyms* — "denim" will never match "jeans".

**Dense vector search** is the opposite. It captures semantic similarity, so with real embeddings "denim" and "jeans" land near each other — but it *dilutes rare keywords*, because a product code is just one token among many in the averaged representation.

The key insight is that **their errors are complementary, not correlated**. BM25 misses exactly the synonym cases vectors catch; vectors miss exactly the rare-keyword cases BM25 nails. Fuse the two rankings and you recover the *union* of what each finds.

### The fusion choice: normalized weighted sum vs RRF

Two rankings can't just be added — a BM25 score of 8.0 and a cosine similarity of 0.6 aren't on the same scale. Two standard fixes:

- **Min-max normalized weighted sum** (what this lab uses). Scale each side's scores into `[0, 1]`, then combine `alpha * vector + (1 - alpha) * bm25`. `alpha` is a dial: 1.0 is pure vector, 0.0 is pure BM25, 0.5 is balanced. It **keeps score magnitudes** — a chunk BM25 scores far above the pack stays clearly ahead — and the `alpha` knob maps directly onto "how much do I trust keywords vs semantics."
- **Reciprocal Rank Fusion (RRF)**. Ignore scores entirely; sum `1 / (rank + 60)` across rankings. It is robust and scale-free, which makes it the better default on **large, noisy corpora** where raw scores are unreliable — but it throws away the magnitude of agreement.

We use the weighted sum for hybrid search (13 documents, score gaps are meaningful) and RRF for multi-query fusion (same retriever, so ranks are the cleaner signal). Neither is universally right; the lab comments say why each was chosen where. *(The shared `retrieve_multi_query` uses RRF; `hybrid_search` uses the weighted sum.)*

---

## 3. Reranking with a cross-encoder

Retrieval gives you a shortlist. Reranking *reorders* that shortlist with a stronger, slower model, then keeps the top few. It fixes failure mode #3 (ranking, not coverage) — and **only** that. A reranker can never add a chunk retrieval didn't fetch, so it is a precision tool, not a recall tool.

### Bi-encoder vs cross-encoder — the whole point

- A **bi-encoder** (your embedding model) encodes the query and each document **separately**, into independent vectors, then compares them with cosine similarity. The two texts never see each other. This is what makes vector search fast and pre-computable: you embed the corpus once, offline.
- A **cross-encoder** feeds the **(query, document) pair through one transformer together**, so its attention layers weigh the interaction between the two directly. It answers "how relevant is *this document* to *this query*?" far more accurately — and cannot be pre-computed, because it needs the query. Running it over a whole corpus per query would be hopelessly slow.

So the pattern is: bi-encoder retrieves a cheap shortlist (say top-20), cross-encoder reranks it precisely down to top-4. Best of both — most of the accuracy, a fraction of the cost.

The lab's live path uses `cross-encoder/ms-marco-MiniLM-L-6-v2` (a small, free, local model that downloads once). Offline, the `OverlapReranker` approximates it with token-overlap scoring — genuinely useful for keyword queries, and **honest that it is only an approximation**: like BM25, it is blind to synonyms and is no substitute for the real cross-encoder's semantic judgment.

---

## 4. Query rewriting, multi-query, and decomposition

The failures so far were about matching a query to chunks. This family fixes the *query itself*.

- **Query rewriting** asks an LLM to rephrase the question toward the vocabulary the corpus is likely to use. "Am I allowed to wear denim?" → "jeans dress code headquarters".
- **Multi-query expansion** generates *several* rewrites, retrieves for each, and fuses (with RRF) the results — so a paraphrase that misses on the original wording gets a second and third chance. A chunk that several rewrites agree on floats to the top.
- **Query decomposition** splits a compound question into sub-questions, retrieves for each, and unions the evidence. "Can support refund me, or does someone else sign off?" becomes "what is the damaged-goods refund policy?" + "what refunds need manager approval?" — the fix for failure mode #4.

All three cost an extra LLM call (to generate the rewrites) plus N× the retrievals. That makes this the **most expensive** stage per query, and — as your measurements will show — the one most likely to *hurt* when the rewrites are weak (a bad rewrite dilutes a good original with off-target chunks).

---

## 5. Parent-document retrieval (concept — the lab stretch)

A tension runs through chunking: **small chunks retrieve precisely** (a tight chunk matches a specific question sharply) but **large chunks answer completely** (the generator needs surrounding context, not a lone sentence).

**Parent-document retrieval** resolves it: index *small* chunks for precise matching, but when a small chunk is retrieved, return its **parent** — the larger section or whole document it came from — to the generator. You search on precision and answer on context. The `Chunk` schema already carries `doc_id` and `index`, so the parent is one lookup away. Implementing it is the lab's stretch goal; here you only need to be able to explain it.

---

## 6. When naive RAG is enough (the anti-hype section)

Every technique above adds latency, cost, and a moving part that can break. The engineering question is never "is this technique good?" — it is "does it help *my* corpus and queries enough to justify its cost?" And the honest answer is often **no**.

Your own measurements in this module make the point better than any lecture. With **real sentence-transformer embeddings** on the TechCorp corpus, the naive baseline already scores **100% hit@4** — there is nothing left for hybrid, rerank, or rewrite to improve. Every advanced config either matches it (adding latency for zero gain) or, in the case of multi-query with weak rewrites, actively *hurts*. The advanced techniques earn their keep on the **hash-embedding** run, where the baseline is weaker and there is headroom to recover.

The lesson generalizes:

- **Naive top-k is enough** when your embeddings are good, your corpus is small and clean, and your users phrase questions in the corpus's vocabulary. Don't add machinery to a system that already scores well — you'll pay latency and complexity for a rounding error.
- **Hybrid search** is the cheapest upgrade and the first to try, *if* your queries carry exact tokens (product codes, error strings, policy names).
- **Reranking** helps only when you've measured that the right chunk is retrieved but ranked too low — a precision problem, not a coverage one.
- **Query rewriting** helps paraphrase-heavy, vague, or compound questions, and is the easiest to make *worse*. Measure before you ship it.

The discipline this module teaches is not "add these four things." It is: **measure the baseline, add one technique, re-measure, and keep it only if the number moved.**

---

## Misconceptions to unlearn

- **"Advanced RAG is strictly better than naive RAG."** No — it is a set of trade-offs. Your live run shows it adding cost for zero gain on a corpus the baseline already aced.
- **"A reranker fixes bad retrieval."** No — it can only reorder what retrieval already fetched. If the right chunk isn't in the shortlist, reranking is powerless. Fix recall (hybrid, multi-query) first.
- **"More rewrites always mean better recall."** No — a weak or off-target rewrite injects irrelevant chunks and can push the right one out of the top-k, *lowering* hit@k. You will see exactly this negative result.
- **"Hybrid means running BM25 and vectors and picking whichever is higher."** No — the value is in *fusing* both scores so agreement is rewarded; picking one throws away the complementarity.
- **"Cross-encoders can replace vector search."** No — they're too slow to run over a whole corpus. They rerank a shortlist retrieval produced.

## Trade-offs to keep in view

- **Every stage adds latency and cost.** Reranking adds a transformer pass over the shortlist; multi-query multiplies retrievals and adds an LLM call. Your report's `latency ms/query` column exists to make this concrete.
- **More moving parts, more failure modes.** A rewrite LLM that returns garbage, a reranker model that fails to download — each new stage is something that can break in production.
- **Measure before adopting, and report negatives honestly.** A configuration that didn't help is not a failed experiment; it is a load-bearing finding that saved you from shipping useless complexity.
