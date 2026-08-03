"""Module 06 tests — reference solution. Always runs, fully offline.

These tests index the REAL TechCorp corpus (data/) with the deterministic
HashEmbeddingClient, so no model download and no network are ever needed.

Honesty note on what is asserted, and why
-----------------------------------------
Hash embeddings measure WORD OVERLAP, not meaning (see Module 05). On the
spec's natural-language queries the hash vectors also contain the query's
filler words ("can", "i", "at", ...), which collide across every chunk and
drown the one discriminative word. Empirically, with hash embeddings the
semantic top-1 for "Can I wear jeans at the office?" is a Remote Work chunk,
NOT the dress code — only real sentence-transformers embeddings rank the
dress code first (run the solution live to see it).

So this suite asserts only what hash embeddings and keyword overlap can
GUARANTEE on this corpus:

- "jeans" appears in exactly one document (hr-dress-code) and "broken" in
  exactly one (support-refund-damaged) → keyword_search, which strips
  stopwords, must put those documents first.
- Word overlap is still signal for hash vectors: the broken-product query
  shares product/arrives/broken with support-refund-damaged, which lands it
  in the semantic top-3 (though not top-1 — filler-word noise again).
- Identical text → identical hash vector → cosine 1.0 (self-similarity),
  which proves the embed→store→rank plumbing without semantics.
- "recover" appears in NO document: the corpus simply has no account-recovery
  policy, so no search variant can return a relevant result for it.
"""

from pathlib import Path

import pytest

from techcorp_agent.config import PROJECT_ROOT
from techcorp_agent.course_utils import import_from_path
from techcorp_agent.documents import load_documents
from techcorp_agent.embeddings import HashEmbeddingClient
from techcorp_agent.schemas import RetrievedChunk

MODULE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

JEANS_QUERY = "Can I wear jeans at the office?"
BROKEN_QUERY = "What happens when a product arrives broken?"
RECOVER_QUERY = "How do I recover my account?"


@pytest.fixture(scope="module")
def solution():
    return import_from_path(
        "m06_solution_search_engine", MODULE_DIR / "solution" / "search_engine.py"
    )


@pytest.fixture(scope="module")
def engine(solution):
    """The solution engine, indexed over the real TechCorp corpus offline."""
    documents = load_documents(DATA_DIR)
    assert len(documents) == 13, "expected the full 13-document TechCorp corpus"
    engine = solution.SearchEngine(HashEmbeddingClient())
    added = engine.index(documents)
    assert added > 0
    return engine


def test_index_stores_aligned_chunks_and_vectors(engine):
    assert len(engine.chunks) == len(engine.vectors), "chunks and vectors must stay parallel"
    assert len(engine.chunks) > len(set(c.doc_id for c in engine.chunks)), (
        "documents should be split into multiple chunks each"
    )
    dimension = engine.embedding_client.dimension
    assert all(len(vector) == dimension for vector in engine.vectors)


def test_search_returns_retrieved_chunks_sorted_descending(engine):
    results = engine.search(BROKEN_QUERY, top_k=10)
    assert results, "searching a non-empty index must return results"
    assert all(isinstance(result, RetrievedChunk) for result in results)
    scores = [result.score for result in results]
    assert scores == sorted(scores, reverse=True), "results must be sorted best-first"


def test_top_k_limits_result_count(engine):
    assert len(engine.search(JEANS_QUERY, top_k=3)) == 3
    assert len(engine.search(JEANS_QUERY, top_k=1)) == 1
    assert len(engine.search(JEANS_QUERY, top_k=10_000)) == len(engine.chunks)


def test_min_score_filters_low_results(engine):
    unfiltered = engine.search(BROKEN_QUERY, top_k=10)
    threshold = unfiltered[2].score
    filtered = engine.search(BROKEN_QUERY, top_k=10, min_score=threshold)
    assert 0 < len(filtered) <= len(unfiltered)
    assert all(result.score >= threshold for result in filtered)
    # An absurdly high threshold keeps nothing: an empty answer, not a crash.
    assert engine.search(BROKEN_QUERY, top_k=10, min_score=0.99) == []


def test_identical_text_scores_one(engine):
    """Self-similarity proves the embed→store→rank plumbing: the exact text of
    an indexed chunk must come back as the top hit with cosine ≈ 1.0 (identical
    text produces the identical vector, whatever the embedding model)."""
    chunk = next(
        c for c in engine.chunks if c.doc_id == "hr-dress-code" and "jeans" in c.text.lower()
    )
    results = engine.search(chunk.text, top_k=2)
    assert results[0].chunk.id == chunk.id
    assert results[0].score == pytest.approx(1.0, abs=1e-9)
    assert results[1].score < results[0].score


def test_keyword_search_jeans_hits_dress_code(engine):
    """'jeans' appears in exactly one corpus document, so keyword overlap
    (stopwords removed) is guaranteed to rank hr-dress-code first."""
    results = engine.keyword_search(JEANS_QUERY, top_k=3)
    assert results, "the query shares words with the corpus — must match"
    assert results[0].chunk.doc_id == "hr-dress-code"
    assert results[0].score > 0


def test_keyword_search_broken_product_hits_refund_damaged(engine):
    """'broken' appears only in support-refund-damaged, which also contains
    'product' and 'arrives' — the highest possible keyword overlap."""
    results = engine.keyword_search(BROKEN_QUERY, top_k=3)
    assert results[0].chunk.doc_id == "support-refund-damaged"


def test_semantic_search_broken_product_reaches_refund_damaged(engine):
    """Even hash vectors carry the product/arrives/broken overlap: the right
    document lands in the semantic top-3. (Top-1 needs real embeddings —
    filler-word buckets add noise that sentence-transformers doesn't have.)"""
    results = engine.search(BROKEN_QUERY, top_k=3)
    assert "support-refund-damaged" in {result.chunk.doc_id for result in results}


def test_account_recovery_has_no_relevant_answer(engine, solution):
    """The corpus contains no account-recovery document at all — 'recover'
    appears in no chunk. Keyword search can only match the generic word
    'account' (privacy/equipment chunks — wrong topic), and hash-semantic
    scores stay so low that a modest threshold returns nothing. Real
    embeddings also retrieve only account-*deletion* chunks here: this query
    is unanswerable by design, which is what thresholds are for."""
    assert all("recover" not in solution.tokenize(chunk.text) for chunk in engine.chunks)

    query_words = solution.tokenize(RECOVER_QUERY)
    for result in engine.keyword_search(RECOVER_QUERY, top_k=5):
        assert query_words & solution.tokenize(result.chunk.text) == {"account"}, (
            "keyword matches must come from the generic word 'account' only"
        )

    assert engine.search(RECOVER_QUERY, top_k=5, min_score=0.25) == [], (
        "no chunk should clear even a modest similarity threshold for this query"
    )


def test_keyword_search_all_stopwords_returns_nothing(engine):
    assert engine.keyword_search("How do I?", top_k=3) == []
