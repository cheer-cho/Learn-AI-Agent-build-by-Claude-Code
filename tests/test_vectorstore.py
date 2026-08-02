from pathlib import Path

import pytest

from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.vectorstore.chroma_store import VectorStore


@pytest.fixture
def store(sample_corpus: Path, tmp_path: Path, hash_embeddings) -> VectorStore:
    store = VectorStore(hash_embeddings, persist_dir=tmp_path / "chroma")
    for doc in load_documents(sample_corpus):
        store.add_chunks(chunk_document(doc))
    return store


def test_add_and_count(store: VectorStore):
    assert store.count() >= 3


def test_query_finds_relevant_document_first(store: VectorStore):
    results = store.query("refund for a damaged product", top_k=3)
    assert results
    assert results[0].chunk.doc_id == "test-refunds"
    assert results[0].score >= results[-1].score


def test_category_filter(store: VectorStore):
    results = store.query("policy", top_k=5, category="product_support")
    assert results
    assert all(r.chunk.category == "product_support" for r in results)


def test_min_score_threshold_drops_weak_matches(store: VectorStore):
    everything = store.query("refund for a damaged product", top_k=5)
    filtered = store.query("refund for a damaged product", top_k=5, min_score=0.99)
    assert len(filtered) <= len(everything)


def test_persistence_across_reopen(sample_corpus: Path, tmp_path: Path, hash_embeddings):
    persist_dir = tmp_path / "chroma"
    first = VectorStore(hash_embeddings, persist_dir=persist_dir)
    for doc in load_documents(sample_corpus):
        first.add_chunks(chunk_document(doc))
    count = first.count()
    assert count > 0

    reopened = VectorStore(hash_embeddings, persist_dir=persist_dir)
    assert reopened.count() == count


def test_embedding_model_mismatch_is_rejected(store: VectorStore, tmp_path: Path):
    other_model = HashEmbeddingClient(dimension=64)  # different model_name
    with pytest.raises(ValueError, match="not comparable"):
        VectorStore(other_model, persist_dir=tmp_path / "chroma")


def test_reset_empties_collection(store: VectorStore):
    assert store.count() > 0
    store.reset()
    assert store.count() == 0


def test_query_on_empty_store_returns_nothing(tmp_path: Path, hash_embeddings):
    store = VectorStore(hash_embeddings, persist_dir=tmp_path / "empty")
    assert store.query("anything") == []
