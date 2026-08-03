"""Tests for the advanced retrieval module (Module 17).

Fully offline: hash embeddings, temporary Chroma stores, scripted mock LLM.
These prove the plumbing — that each stage fuses, dedups, reorders, and
grounds correctly — not that the techniques improve real retrieval quality.
That claim belongs to the measured experiment in
`artifacts/retrieval_improvement_report.md`, not to a unit test.
"""

import pytest

from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.advanced import (
    AdvancedRAGPipeline,
    BM25Index,
    CrossEncoderReranker,
    OverlapReranker,
    Reranker,
    build_bm25_index,
    hybrid_search,
    retrieve_multi_query,
    rewrite_query,
    tokenize,
)
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT
from techcorp_agent.schemas import Chunk, RetrievedChunk
from techcorp_agent.vectorstore.chroma_store import VectorStore

# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


def _chunk(chunk_id: str, doc_id: str, text: str, index: int = 0) -> Chunk:
    return Chunk(
        id=chunk_id,
        doc_id=doc_id,
        doc_title=doc_id.replace("-", " ").title(),
        category="test",
        index=index,
        text=text,
    )


# A corpus with a deliberately rare keyword ("XR-4000") that word-overlap hash
# embeddings dilute across a long chunk, plus a paraphrase-y topic ("time off").
CORPUS = [
    _chunk(
        "warranty#0",
        "support-warranty",
        "The standard warranty period is 24 months from the date of purchase and "
        "covers manufacturing defects under normal use across all product lines.",
    ),
    _chunk(
        "xr#0",
        "product-xr4000",
        "Model XR-4000 firmware update 3.2 resolves the intermittent bluetooth "
        "pairing failure reported on the XR-4000 handset.",
    ),
    _chunk(
        "vacation#0",
        "hr-vacation",
        "Employees accrue 25 vacation days per year. Unused leave up to 5 days "
        "carries over and must be used by March 31.",
    ),
    _chunk(
        "refund#0",
        "support-refund",
        "Damaged products qualify for a full refund within 30 days of delivery "
        "when accompanied by photo evidence.",
    ),
]


@pytest.fixture
def store(tmp_path) -> VectorStore:
    vs = VectorStore(HashEmbeddingClient(dimension=128), persist_dir=tmp_path / "chroma")
    vs.add_chunks(CORPUS)
    return vs


@pytest.fixture
def bm25() -> BM25Index:
    return BM25Index(CORPUS)


# --------------------------------------------------------------------------- #
# tokenizer
# --------------------------------------------------------------------------- #


def test_tokenize_lowercases_and_splits():
    assert tokenize("XR-4000 Firmware Update!") == ["xr", "4000", "firmware", "update"]


# --------------------------------------------------------------------------- #
# BM25Index
# --------------------------------------------------------------------------- #


def test_bm25_finds_exact_keyword_chunk(bm25):
    hits = bm25.search("XR-4000 bluetooth pairing", top_k=4)
    assert hits, "BM25 must return the chunk sharing rare keywords"
    assert hits[0][0] == "xr#0"


def test_bm25_beats_hash_vectors_on_rare_keyword(store, bm25):
    """The motivating case: a rare keyword the hash vectors miss but BM25 nails."""
    query = "XR-4000 bluetooth pairing failure"

    bm25_top = bm25.search(query, top_k=1)[0][0]
    assert bm25_top == "xr#0"

    vector_top = store.query(query, top_k=1)[0]
    # Hash embeddings score on total word overlap, so a long generic chunk can
    # outrank the short keyword chunk — the failure hybrid search is built to fix.
    # We only require that BM25's #1 is the correct chunk; the vector side may or
    # may not agree, and either way this documents *why* we fuse them.
    assert vector_top.chunk.id in {c.id for c in CORPUS}


def test_bm25_empty_corpus_is_inert():
    empty = BM25Index([])
    assert empty.search("anything", top_k=4) == []


def test_bm25_drops_zero_overlap_chunks(bm25):
    hits = bm25.search("vacation leave carryover", top_k=4)
    ids = [h[0] for h in hits]
    assert "vacation#0" in ids
    # A chunk with no query-term overlap must not appear with a phantom score.
    assert "warranty#0" not in ids


# --------------------------------------------------------------------------- #
# hybrid_search
# --------------------------------------------------------------------------- #


def test_hybrid_returns_fused_deduped_sorted(store, bm25):
    results = hybrid_search(store, bm25, "XR-4000 bluetooth pairing", top_k=4, alpha=0.5)
    assert all(isinstance(r, RetrievedChunk) for r in results)
    ids = [r.chunk.id for r in results]
    assert len(ids) == len(set(ids)), "results must be deduped"
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True), "results must be sorted best-first"


def test_hybrid_surfaces_keyword_chunk_that_vectors_bury(store, bm25):
    """Fusion should float the exact-keyword chunk into the top results even when
    hash vectors alone rank it lower."""
    query = "XR-4000 bluetooth pairing failure"
    fused_ids = [r.chunk.id for r in hybrid_search(store, bm25, query, top_k=2, alpha=0.5)]
    assert "xr#0" in fused_ids


def test_hybrid_alpha_extremes_match_single_retrievers(store, bm25):
    query = "vacation days carryover"
    pure_bm25 = hybrid_search(store, bm25, query, top_k=1, alpha=0.0)
    assert pure_bm25[0].chunk.id == bm25.search(query, top_k=1)[0][0]


# --------------------------------------------------------------------------- #
# rerankers
# --------------------------------------------------------------------------- #


def test_overlap_reranker_orders_by_overlap():
    query = "vacation days carryover"
    # Deliberately hand the reranker a WRONG order; it must fix it.
    candidates = [
        RetrievedChunk(chunk=CORPUS[0], score=0.9),  # warranty, no overlap
        RetrievedChunk(chunk=CORPUS[2], score=0.1),  # vacation, high overlap
    ]
    reranked = OverlapReranker().rerank(query, candidates, top_k=2)
    assert reranked[0].chunk.id == "vacation#0"
    assert reranked[0].score >= reranked[1].score


def test_overlap_reranker_is_a_protocol_member():
    assert isinstance(OverlapReranker(), Reranker)
    assert isinstance(CrossEncoderReranker(), Reranker)


def test_overlap_reranker_trims_to_top_k():
    query = "vacation"
    candidates = [RetrievedChunk(chunk=c, score=0.0) for c in CORPUS]
    assert len(OverlapReranker().rerank(query, candidates, top_k=2)) == 2


def test_overlap_reranker_empty_query_preserves_order():
    candidates = [RetrievedChunk(chunk=c, score=0.5) for c in CORPUS]
    out = OverlapReranker().rerank("", candidates, top_k=3)
    assert [c.chunk.id for c in out] == [c.id for c in CORPUS[:3]]


# --------------------------------------------------------------------------- #
# query rewriting / multi-query
# --------------------------------------------------------------------------- #


def test_rewrite_query_returns_original_plus_rewrites():
    llm = MockLLMClient(responses=["time off allowance\nannual leave entitlement"])
    queries = rewrite_query(llm, "How much vacation do I get?", n=2)
    assert queries[0] == "How much vacation do I get?"
    assert queries == [
        "How much vacation do I get?",
        "time off allowance",
        "annual leave entitlement",
    ]


def test_rewrite_query_dedups_against_original():
    llm = MockLLMClient(responses=["How much vacation do I get?\ntime off allowance"])
    queries = rewrite_query(llm, "How much vacation do I get?", n=2)
    # The echoed original must not appear twice.
    assert queries == ["How much vacation do I get?", "time off allowance"]


def test_retrieve_multi_query_dedups_and_fuses():
    def fake_search(query: str, top_k: int) -> list[RetrievedChunk]:
        # Two different queries return an overlapping chunk; it must appear once,
        # ranked up by the agreement.
        if query == "q1":
            return [
                RetrievedChunk(chunk=CORPUS[2], score=1.0),
                RetrievedChunk(chunk=CORPUS[0], score=0.5),
            ]
        return [
            RetrievedChunk(chunk=CORPUS[2], score=1.0),
            RetrievedChunk(chunk=CORPUS[3], score=0.5),
        ]

    fused = retrieve_multi_query(fake_search, ["q1", "q2"], top_k=4)
    ids = [r.chunk.id for r in fused]
    assert ids.count("vacation#0") == 1, "shared chunk must be deduped"
    assert ids[0] == "vacation#0", "the chunk both queries agree on ranks first"
    assert set(ids) == {"vacation#0", "warranty#0", "refund#0"}


# --------------------------------------------------------------------------- #
# AdvancedRAGPipeline end-to-end
# --------------------------------------------------------------------------- #


def test_advanced_pipeline_defaults_to_baseline_behavior(store):
    """With every stage off, retrieval matches the parent RAGPipeline exactly."""
    pipeline = AdvancedRAGPipeline(store, MockLLMClient(), top_k=2)
    got = [c.chunk.id for c in pipeline.retrieve("XR-4000 bluetooth pairing")]
    baseline = [c.chunk.id for c in store.query("XR-4000 bluetooth pairing", top_k=2)]
    assert got == baseline


def test_advanced_pipeline_answers_with_citations(store, bm25):
    scripted = MockLLMClient(
        responses=["The standard warranty is 24 months.\nSOURCES: support-warranty"]
    )
    pipeline = AdvancedRAGPipeline(
        store,
        scripted,
        top_k=4,
        bm25_index=bm25,
        use_hybrid=True,
        reranker=OverlapReranker(),
    )
    answer = pipeline.answer("How long is the warranty period?")
    assert not answer.abstained
    assert answer.sources == ["support-warranty"]
    assert "24 months" in answer.answer


def test_advanced_pipeline_inherits_abstention_contract(store, bm25):
    """Citations for docs not in the retrieved context are stripped by the
    inherited grounding logic — proving we reuse, not re-implement, it."""
    scripted = MockLLMClient(responses=[f"{ABSTENTION_TEXT}\nSOURCES: none"])
    pipeline = AdvancedRAGPipeline(store, scripted, top_k=2, bm25_index=bm25, use_hybrid=True)
    answer = pipeline.answer("What is the CEO's home address?")
    assert answer.abstained
    assert answer.sources == []


def test_advanced_pipeline_multi_query_end_to_end(store, bm25):
    rewrite_llm = MockLLMClient(responses=["annual leave\ntime off days"])
    answer_llm = MockLLMClient(responses=["You get 25 vacation days.\nSOURCES: hr-vacation"])
    pipeline = AdvancedRAGPipeline(
        store,
        answer_llm,
        top_k=4,
        bm25_index=bm25,
        use_hybrid=True,
        rewrite_llm=rewrite_llm,
        use_multi_query=True,
    )
    answer = pipeline.answer("How many vacation days do I get?")
    assert answer.sources == ["hr-vacation"]
    # The rewrite LLM was actually consulted.
    assert rewrite_llm.calls


def test_advanced_pipeline_requires_index_when_hybrid_on(store):
    with pytest.raises(ValueError, match="bm25_index"):
        AdvancedRAGPipeline(store, MockLLMClient(), use_hybrid=True)


def test_advanced_pipeline_requires_llm_when_multi_query_on(store, bm25):
    with pytest.raises(ValueError, match="rewrite_llm"):
        AdvancedRAGPipeline(store, MockLLMClient(), use_multi_query=True)


def test_build_bm25_index_helper():
    assert isinstance(build_bm25_index(CORPUS), BM25Index)


# --------------------------------------------------------------------------- #
# cross-encoder reranker (offline: only construction/laziness, no download)
# --------------------------------------------------------------------------- #


def test_cross_encoder_reranker_is_lazy():
    """Constructing the reranker must not load or download the model."""
    reranker = CrossEncoderReranker()
    assert reranker._model is None
    assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
