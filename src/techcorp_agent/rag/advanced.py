"""Advanced retrieval for the TechCorp RAG pipeline (Module 17).

Module 08 gives us naive top-k vector retrieval; Module 09 measures it and
finds the honest weak spot recorded in `artifacts/evaluation_report.md`: with
hash embeddings, paraphrase questions hit@4 only **60%** while the corpus
overall sits at **88%**. This module adds the four standard retrieval upgrades
so the Module 09 evaluation can be re-run and the *measured* effect of each
reported — including the honest negative results.

Everything here is additive: it imports the reference `RAGPipeline` and reuses
its grounding/citation contract unchanged. It never edits `pipeline.py`.

The four techniques:

- **Hybrid search** (`BM25Index` + `hybrid_search`): fuse a lexical BM25 rank
  with the vector rank. BM25 and embeddings fail *differently* — BM25 nails
  exact keywords/rare tokens but is blind to synonyms; vectors catch synonyms
  but (especially with hash embeddings) drown a rare keyword in generic word
  overlap. Fusing them recovers the union of what each finds.
- **Reranking** (`Reranker` protocol → `CrossEncoderReranker`,
  `OverlapReranker`): re-score a shortlist with a stronger, slower model. A
  cross-encoder reads the (query, chunk) pair jointly; the offline
  `OverlapReranker` is a deterministic token-overlap approximation, honest
  about being only that.
- **Query rewriting / multi-query** (`rewrite_query`,
  `retrieve_multi_query`): expand one question into several phrasings, retrieve
  for each, and fuse — so a paraphrase that misses on the original wording can
  be rescued by a rewrite that shares the corpus's vocabulary.
- **AdvancedRAGPipeline**: a configurable `RAGPipeline` subclass that toggles
  each stage independently, so the experiment can isolate each one's effect.

Why subclass rather than compose: the pipeline's value is the grounding
contract in `build_messages`/`answer`/`parse_answer`. We only want to override
*retrieval*. Subclassing and overriding `retrieve()` reuses the entire
generation path verbatim — the augment→generate→cite→abstain guarantees are
inherited, not re-implemented, so they cannot silently drift.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from techcorp_agent.llm.base import LLMClient
from techcorp_agent.rag.pipeline import RAGPipeline
from techcorp_agent.schemas import ChatMessage, Chunk, RetrievedChunk
from techcorp_agent.vectorstore.chroma_store import VectorStore

# A retrieval function: question -> ranked chunks. Both `VectorStore.query` (via
# a small adapter) and `hybrid_search` conform, which is what lets
# `retrieve_multi_query` stay agnostic about how each query is answered.
SearchFn = Callable[[str, int], list[RetrievedChunk]]

_WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word/number tokenizer shared by BM25 and the overlap reranker.

    Deliberately simple (no stemming, no stopword list): it is deterministic,
    dependency-free, and matches the spirit of `HashEmbeddingClient`'s
    tokenizer so the offline numbers are reproducible on any machine.
    """
    return _WORD_RE.findall(text.lower())


# --------------------------------------------------------------------------- #
# BM25 lexical index
# --------------------------------------------------------------------------- #


class BM25Index:
    """A BM25 (Okapi) keyword index over a fixed set of chunks.

    BM25 scores by term frequency and inverse document frequency: rare query
    words that appear in a chunk drive the score up hard. That is exactly the
    signal dense embeddings underweight, which is why the two combine well.

    Backed by `rank_bm25.BM25Okapi`, whose API is `BM25Okapi(corpus_tokens)`
    (a list of token lists) and `.get_scores(query_tokens)` (one raw score per
    corpus document, same order as the corpus).
    """

    def __init__(self, chunks: list[Chunk]):
        from rank_bm25 import BM25Okapi

        self._chunks = list(chunks)
        self._by_id = {chunk.id: chunk for chunk in self._chunks}
        corpus_tokens = [tokenize(chunk.text) for chunk in self._chunks]
        # BM25Okapi rejects an empty corpus; guard so an empty store is inert
        # rather than an exception at construction time.
        self._bm25 = BM25Okapi(corpus_tokens) if corpus_tokens else None

    @property
    def chunks(self) -> list[Chunk]:
        return self._chunks

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        return self._by_id.get(chunk_id)

    def search(self, query: str, top_k: int = 4) -> list[tuple[str, float]]:
        """Return up to `top_k` (chunk_id, bm25_score) pairs, best first.

        Chunks with a non-positive BM25 score (no query term overlap) are
        dropped: a zero score is not a weak match, it is *no* match, and
        keeping it would pollute score fusion with meaningless entries.
        """
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(
            ((chunk.id, float(score)) for chunk, score in zip(self._chunks, scores, strict=True)),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return [(chunk_id, score) for chunk_id, score in ranked[:top_k] if score > 0.0]


# --------------------------------------------------------------------------- #
# Hybrid search: score fusion
# --------------------------------------------------------------------------- #


def _min_max_normalize(scores: dict[str, float]) -> dict[str, float]:
    """Scale a {id: score} map into [0, 1] by min-max.

    Vector similarities (~[-1, 1] cosine) and BM25 scores (unbounded, corpus
    dependent) live on incompatible scales, so a raw weighted sum would let
    whichever scorer happens to emit bigger numbers dominate. Min-max puts both
    on a common [0, 1] axis first. When every score is equal (or there is one
    item) the range is zero and each maps to 1.0 — it was retrieved, so it is a
    full match on its own scale.
    """
    if not scores:
        return {}
    values = scores.values()
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return {key: 1.0 for key in scores}
    return {key: (value - lo) / (hi - lo) for key, value in scores.items()}


def hybrid_search(
    vector_store: VectorStore,
    bm25_index: BM25Index,
    query: str,
    top_k: int = 4,
    alpha: float = 0.5,
    candidate_k: int | None = None,
) -> list[RetrievedChunk]:
    """Fuse vector and BM25 rankings into one ranked chunk list.

    Fusion strategy: **min-max normalized weighted sum**.

        fused = alpha * norm(vector_score) + (1 - alpha) * norm(bm25_score)

    `alpha` weights the dense (vector) side; `alpha=1.0` is pure vector,
    `alpha=0.0` is pure BM25, `0.5` is balanced. A chunk missing from one
    ranking contributes 0 on that side (not retrieved there), so a chunk found
    by both is rewarded over one found by only a single retriever.

    Why min-max weighted sum over Reciprocal Rank Fusion (RRF): RRF discards
    the *magnitude* of agreement (it only sees ranks), and with a tiny 13-doc
    corpus the score gaps carry real signal — a chunk BM25 scores far above the
    rest should outrank one that merely edged into a list. Min-max keeps that
    magnitude while still making the two scales comparable. The `alpha` knob
    also maps directly onto the "how much do I trust keywords vs semantics"
    intuition the lab builds. RRF is the better default on large, noisy
    corpora; we note that trade-off in concepts.md rather than hide it.

    Each retriever searches `candidate_k` (default `max(top_k, 10)`) so fusion
    can reorder a real shortlist instead of two pre-truncated top-k lists.
    """
    pool = candidate_k or max(top_k, 10)

    vector_hits = vector_store.query(query, top_k=pool, min_score=None)
    bm25_hits = bm25_index.search(query, top_k=pool)

    # Remember the chunk object for every id we might return. Prefer the vector
    # hit's chunk (it already carries a similarity score); fall back to the
    # BM25 index for chunks only the lexical side found.
    chunk_by_id: dict[str, Chunk] = {hit.chunk.id: hit.chunk for hit in vector_hits}
    for chunk_id, _ in bm25_hits:
        if chunk_id not in chunk_by_id:
            chunk = bm25_index.get_chunk(chunk_id)
            if chunk is not None:
                chunk_by_id[chunk_id] = chunk

    vector_norm = _min_max_normalize({hit.chunk.id: hit.score for hit in vector_hits})
    bm25_norm = _min_max_normalize(dict(bm25_hits))

    fused: list[RetrievedChunk] = []
    for chunk_id, chunk in chunk_by_id.items():
        score = alpha * vector_norm.get(chunk_id, 0.0) + (1.0 - alpha) * bm25_norm.get(
            chunk_id, 0.0
        )
        fused.append(RetrievedChunk(chunk=chunk, score=score))

    fused.sort(key=lambda item: item.score, reverse=True)
    return fused[:top_k]


# --------------------------------------------------------------------------- #
# Reranking
# --------------------------------------------------------------------------- #


@runtime_checkable
class Reranker(Protocol):
    """Re-score a candidate list against the query, returning the best `top_k`.

    A reranker never *adds* candidates — it can only reorder and trim what
    retrieval already found. If the right chunk was not retrieved, no reranker
    can save the answer; that is why reranking sits *after* (hybrid) retrieval,
    not instead of it.
    """

    def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]: ...


class CrossEncoderReranker:
    """Rerank with a sentence-transformers cross-encoder (live path).

    A bi-encoder (the embedding model) encodes query and document separately,
    then compares vectors — fast, but the two never "see" each other. A
    cross-encoder feeds the (query, chunk) pair through one transformer
    together, so attention can weigh their interaction directly. That is more
    accurate and far too slow to run over a whole corpus — which is exactly why
    it reranks a small shortlist rather than replacing retrieval.

    The model (`cross-encoder/ms-marco-MiniLM-L-6-v2`, ~80 MB) downloads once
    on first use and is cached; loading is lazy so importing this module stays
    cheap and offline. `CrossEncoder.predict([[query, text], ...])` returns one
    relevance score per pair.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        if not chunks:
            return []
        model = self._load()
        scores = model.predict([[query, item.chunk.text] for item in chunks])
        rescored = [
            RetrievedChunk(chunk=item.chunk, score=float(score))
            for item, score in zip(chunks, scores, strict=True)
        ]
        rescored.sort(key=lambda item: item.score, reverse=True)
        return rescored[:top_k]


class OverlapReranker:
    """Deterministic offline reranker: rank by query/chunk token overlap.

    This is an *approximation* of a cross-encoder, not a substitute for one. It
    scores a chunk by how many distinct query tokens it contains, normalized by
    the query length (a Jaccard-style overlap). That rewards chunks that
    literally mention the question's words — genuinely useful for keyword-heavy
    queries, and honest about its blind spot: like BM25 and hash embeddings, it
    cannot tell that "time off" answers "vacation". It exists so the reranking
    *stage* is testable and runnable with zero downloads; the real quality
    signal comes from `CrossEncoderReranker` on the live path.
    """

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        query_tokens = set(tokenize(query))
        if not query_tokens:
            return chunks[:top_k]

        rescored: list[RetrievedChunk] = []
        for item in chunks:
            chunk_tokens = set(tokenize(item.chunk.text))
            overlap = len(query_tokens & chunk_tokens) / len(query_tokens)
            rescored.append(RetrievedChunk(chunk=item.chunk, score=overlap))
        # Stable sort: ties keep the incoming (retrieval) order, so the reranker
        # never *worsens* a shortlist it has no opinion about.
        rescored.sort(key=lambda item: item.score, reverse=True)
        return rescored[:top_k]


# --------------------------------------------------------------------------- #
# Query rewriting / multi-query expansion
# --------------------------------------------------------------------------- #

REWRITE_SYSTEM_PROMPT = """You rewrite a user's question into alternative search queries.

Goal: surface documents that use different wording than the question. Produce
short, keyword-rich reformulations that a search engine would match well.

Rules:
1. Output ONLY the rewritten queries, one per line.
2. Do not number them, quote them, or add any commentary.
3. Keep each rewrite focused on the same information need."""


def rewrite_query(llm: LLMClient, question: str, n: int = 2) -> list[str]:
    """Expand `question` into `[original, *rewrites]` for multi-query retrieval.

    The original is always kept first (never trade a working query for a
    rewrite), followed by up to `n` deduplicated rewrites the LLM proposes.
    Offline this is driven by a scripted `MockLLMClient`, so the rewrites are
    predictable; live, a real model paraphrases toward the corpus's vocabulary.

    A rewrite equal (case-insensitively) to the original or to an earlier
    rewrite is dropped — running the same query twice only wastes a retrieval.
    """
    messages = [
        ChatMessage(role="system", content=REWRITE_SYSTEM_PROMPT),
        ChatMessage(role="user", content=f"Question: {question}\n\nGive {n} alternative queries."),
    ]
    result = llm.complete(messages)
    candidates = [line.strip() for line in result.content.splitlines() if line.strip()]

    queries = [question]
    seen = {question.lower()}
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        queries.append(candidate)
        if len(queries) >= n + 1:
            break
    return queries


def retrieve_multi_query(
    search_fn: SearchFn, queries: list[str], top_k: int = 4
) -> list[RetrievedChunk]:
    """Retrieve for each query, then fuse into one deduped, ranked list.

    Fusion here is Reciprocal Rank Fusion (RRF): each query contributes
    `1 / (rank + K)` to every chunk it retrieves (K=60, the standard constant),
    summed across queries. RRF is the right tool *here* — unlike hybrid search,
    the lists being fused come from the same retriever, so their score scales
    already match and rank position is the cleaner signal; RRF also naturally
    rewards a chunk that several rewrites agree on, which is exactly the
    consensus multi-query is trying to capture.

    A chunk retrieved by multiple queries is kept once, with its scores summed,
    so agreement across rewrites floats it up.
    """
    rrf_k = 60
    fused_score: dict[str, float] = {}
    chunk_by_id: dict[str, Chunk] = {}
    for query in queries:
        for rank, item in enumerate(search_fn(query, top_k)):
            chunk_id = item.chunk.id
            chunk_by_id.setdefault(chunk_id, item.chunk)
            fused_score[chunk_id] = fused_score.get(chunk_id, 0.0) + 1.0 / (rank + rrf_k)

    ranked = sorted(fused_score.items(), key=lambda pair: pair[1], reverse=True)
    return [RetrievedChunk(chunk=chunk_by_id[chunk_id], score=score) for chunk_id, score in ranked][
        :top_k
    ]


# --------------------------------------------------------------------------- #
# The configurable advanced pipeline
# --------------------------------------------------------------------------- #


class AdvancedRAGPipeline(RAGPipeline):
    """A `RAGPipeline` with toggleable retrieval upgrades.

    Only `retrieve()` is overridden; `build_messages`, `answer`, citation
    filtering, and abstention are inherited from `RAGPipeline` unchanged, so the
    grounding contract is shared, not copied. Every stage defaults off, making
    this pipeline identical to the Module 08 baseline until a stage is enabled —
    the property the experiment relies on to attribute each measured delta to
    exactly one technique.

    Stages (applied in order when enabled):

    1. **hybrid** — fuse BM25 with vector search (requires `bm25_index`).
    2. **multi-query** — rewrite the question and fuse retrievals (requires
       `rewrite_llm`; wraps whichever base search stage 1 selected).
    3. **rerank** — re-score the shortlist with `reranker`.

    To let reranking see a real shortlist, retrieval fetches
    `retrieve_k = max(top_k, rerank_pool)` candidates and the reranker trims
    back to `top_k`. Without a reranker, only `top_k` are fetched.
    """

    def __init__(
        self,
        store: VectorStore,
        llm: LLMClient,
        *,
        top_k: int = 4,
        min_score: float | None = None,
        bm25_index: BM25Index | None = None,
        use_hybrid: bool = False,
        alpha: float = 0.5,
        reranker: Reranker | None = None,
        rerank_pool: int = 10,
        rewrite_llm: LLMClient | None = None,
        use_multi_query: bool = False,
        n_rewrites: int = 2,
    ):
        # min_score defaults to None here: fused/reranked scores are on a
        # different scale than raw cosine, so the base pipeline's 0.05 cosine
        # floor would be meaningless once a stage is on.
        super().__init__(store, llm, top_k=top_k, min_score=min_score)
        self._bm25_index = bm25_index
        self._use_hybrid = use_hybrid
        self._alpha = alpha
        self._reranker = reranker
        self._rerank_pool = rerank_pool
        self._rewrite_llm = rewrite_llm
        self._use_multi_query = use_multi_query
        self._n_rewrites = n_rewrites

        if use_hybrid and bm25_index is None:
            raise ValueError("use_hybrid=True requires a bm25_index")
        if use_multi_query and rewrite_llm is None:
            raise ValueError("use_multi_query=True requires a rewrite_llm")

    def _base_search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        """One retrieval, honoring the hybrid toggle. This is the unit the
        multi-query fuser calls once per rewritten query."""
        if self._use_hybrid and self._bm25_index is not None:
            return hybrid_search(
                self._store,
                self._bm25_index,
                query,
                top_k=top_k,
                alpha=self._alpha,
            )
        return self._store.query(query, top_k=top_k, min_score=self._min_score)

    def retrieve(self, question: str) -> list[RetrievedChunk]:
        # Fetch a wider pool when a reranker will trim it back down.
        retrieve_k = max(self._top_k, self._rerank_pool) if self._reranker else self._top_k

        if self._use_multi_query and self._rewrite_llm is not None:
            queries = rewrite_query(self._rewrite_llm, question, n=self._n_rewrites)
            chunks = retrieve_multi_query(self._base_search, queries, top_k=retrieve_k)
        else:
            chunks = self._base_search(question, retrieve_k)

        if self._reranker is not None:
            chunks = self._reranker.rerank(question, chunks, top_k=self._top_k)
        return chunks[: self._top_k]


def build_bm25_index(store_chunks: list[Chunk]) -> BM25Index:
    """Convenience constructor kept next to the pipeline for symmetry."""
    return BM25Index(store_chunks)
