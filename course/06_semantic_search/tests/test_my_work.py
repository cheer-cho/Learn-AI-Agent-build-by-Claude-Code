"""Module 06 tests — your starter implementation.

These auto-skip while starter/search_engine.py still contains TODO markers.
Once you finish the lab, they run and become your completion gate:

    uv run pytest course/06_semantic_search -q

Everything runs offline against the deterministic HashEmbeddingClient — see
the honesty note at the top of test_solution.py for why the assertions are
phrased around word overlap rather than real semantics.
"""

from pathlib import Path

import pytest

from techcorp_agent.config import PROJECT_ROOT
from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.documents import load_documents
from techcorp_agent.embeddings import HashEmbeddingClient
from techcorp_agent.schemas import RetrievedChunk

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"
DATA_DIR = PROJECT_ROOT / "data"

JEANS_QUERY = "Can I wear jeans at the office?"
BROKEN_QUERY = "What happens when a product arrives broken?"
RECOVER_QUERY = "How do I recover my account?"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/search_engine.py still contains TODO markers — finish the lab first",
)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path(
        "m06_starter_search_engine", STARTER_DIR / "search_engine.py"
    )


@pytest.fixture(scope="module")
def engine(my_work):
    """Your engine, indexed over the real TechCorp corpus offline."""
    documents = load_documents(DATA_DIR)
    assert len(documents) == 13, "expected the full 13-document TechCorp corpus"
    engine = my_work.SearchEngine(HashEmbeddingClient())
    added = engine.index(documents)
    assert added > 0, "index() must return the number of chunks added"
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
    assert engine.search(BROKEN_QUERY, top_k=10, min_score=0.99) == []


def test_identical_text_scores_one(engine):
    """Self-similarity: the exact text of an indexed chunk must come back as
    the top hit with cosine ≈ 1.0 — this proves your embed→store→rank wiring."""
    chunk = next(c for c in engine.chunks if c.doc_id == "hr-dress-code" and "jeans" in c.text.lower())
    results = engine.search(chunk.text, top_k=2)
    assert results[0].chunk.id == chunk.id
    assert results[0].score == pytest.approx(1.0, abs=1e-9)
    assert results[1].score < results[0].score


def test_keyword_search_jeans_hits_dress_code(engine):
    results = engine.keyword_search(JEANS_QUERY, top_k=3)
    assert results, "the query shares words with the corpus — must match"
    assert results[0].chunk.doc_id == "hr-dress-code"
    assert results[0].score > 0


def test_keyword_search_broken_product_hits_refund_damaged(engine):
    results = engine.keyword_search(BROKEN_QUERY, top_k=3)
    assert results[0].chunk.doc_id == "support-refund-damaged"


def test_semantic_search_broken_product_reaches_refund_damaged(engine):
    results = engine.search(BROKEN_QUERY, top_k=3)
    assert "support-refund-damaged" in {result.chunk.doc_id for result in results}


def test_account_recovery_has_no_relevant_answer(engine, my_work):
    """No account-recovery document exists in the corpus — see test_solution.py."""
    assert all("recover" not in my_work.tokenize(chunk.text) for chunk in engine.chunks)

    query_words = my_work.tokenize(RECOVER_QUERY)
    for result in engine.keyword_search(RECOVER_QUERY, top_k=5):
        assert query_words & my_work.tokenize(result.chunk.text) == {"account"}, (
            "keyword matches must come from the generic word 'account' only"
        )

    assert engine.search(RECOVER_QUERY, top_k=5, min_score=0.25) == []


def test_keyword_search_all_stopwords_returns_nothing(engine):
    assert engine.keyword_search("How do I?", top_k=3) == []
