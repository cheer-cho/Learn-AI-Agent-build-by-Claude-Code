from pathlib import Path

import pytest

from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT, RAGPipeline, parse_answer
from techcorp_agent.vectorstore.chroma_store import VectorStore


@pytest.fixture
def store(sample_corpus: Path, tmp_path: Path, hash_embeddings) -> VectorStore:
    store = VectorStore(hash_embeddings, persist_dir=tmp_path / "chroma")
    for doc in load_documents(sample_corpus):
        store.add_chunks(chunk_document(doc))
    return store


def test_parse_answer_extracts_sources():
    answer, sources = parse_answer("Jeans are allowed.\n\nSOURCES: test-dress-code")
    assert answer == "Jeans are allowed."
    assert sources == ["test-dress-code"]


def test_parse_answer_handles_none_and_missing():
    assert parse_answer("Answer.\nSOURCES: none") == ("Answer.", [])
    assert parse_answer("No sources line at all.") == ("No sources line at all.", [])


def test_parse_answer_deduplicates():
    _, sources = parse_answer("A.\nSOURCES: a, b, a")
    assert sources == ["a", "b"]


def test_grounded_answer_with_citations(store: VectorStore):
    llm = MockLLMClient(
        responses=["Yes, jeans are allowed at headquarters.\nSOURCES: test-dress-code"]
    )
    pipeline = RAGPipeline(store, llm)
    result = pipeline.answer("Can I wear jeans at the office dress code?")
    assert result.abstained is False
    assert result.sources == ["test-dress-code"]
    assert "jeans" in result.answer.lower()
    # The grounded prompt must have carried the retrieved context.
    user_message = llm.calls[0][1].content
    assert "[source: test-dress-code]" in user_message


def test_hallucinated_sources_are_dropped(store: VectorStore):
    llm = MockLLMClient(responses=["Answer.\nSOURCES: not-a-real-doc"])
    result = RAGPipeline(store, llm).answer("dress code jeans headquarters")
    assert result.sources == []


def test_abstains_without_llm_call_when_nothing_retrieved(store: VectorStore):
    llm = MockLLMClient(responses=["should never be used"])
    pipeline = RAGPipeline(store, llm, min_score=0.999)  # threshold nothing can pass
    result = pipeline.answer("What is the policy for working from the Moon?")
    assert result.abstained is True
    assert result.answer == ABSTENTION_TEXT
    assert result.sources == []
    assert llm.calls == []  # no credits spent on hopeless retrieval


def test_model_abstention_is_detected(store: VectorStore):
    llm = MockLLMClient(responses=[f"{ABSTENTION_TEXT}\nSOURCES: none"])
    result = RAGPipeline(store, llm).answer("dress code question with weak evidence")
    assert result.abstained is True
    assert result.sources == []
