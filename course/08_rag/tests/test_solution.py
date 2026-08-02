"""Module 08 tests — reference solution. Always runs, fully offline.

Covers the six required RAG scenarios against a small controlled corpus
(written to tmp so hash-embedding retrieval is deterministic), plus the
SOURCES-line parsing edge cases and hallucinated-citation filtering.
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT
from techcorp_agent.vectorstore.chroma_store import VectorStore

MODULE_DIR = Path(__file__).resolve().parents[1]

DOC_TEMPLATE = """---
id: {doc_id}
title: {title}
category: test
tags: [test]
---
# {title}

{body}
"""

# Short, vocabulary-focused documents: with hash embeddings (word overlap),
# each test question below deterministically retrieves the intended documents.
CORPUS = {
    "test-dress-code": (
        "Dress Code",
        "Business casual is the default dress code at TechCorp. "
        "Jeans are allowed at headquarters offices.",
    ),
    "test-vacation": (
        "Vacation Policy",
        "Full-time employees receive twenty days of paid vacation per year, accrued monthly.",
    ),
    "test-returns": (
        "Standard Return Policy",
        "Opened products returned voluntarily incur a fifteen percent restocking fee.",
    ),
    "test-damaged": (
        "Damaged Product Refunds",
        "Products that arrive damaged receive a full refund with no restocking fee.",
    ),
    "test-remote-work": (
        "Remote Work Policy",
        "Employees may work remotely up to three days per week "
        "within their country of employment.",
    ),
    "test-international": (
        "International Remote Work",
        "Working remotely from another country requires manager approval "
        "and is limited to thirty days per year.",
    ),
}


@pytest.fixture(scope="module")
def rag():
    return import_from_path("m08_solution_my_rag", MODULE_DIR / "solution" / "my_rag.py")


@pytest.fixture
def store(tmp_path: Path) -> VectorStore:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for doc_id, (title, body) in CORPUS.items():
        (data_dir / f"{doc_id}.md").write_text(
            DOC_TEMPLATE.format(doc_id=doc_id, title=title, body=body), encoding="utf-8"
        )
    store = VectorStore(HashEmbeddingClient(dimension=128), persist_dir=tmp_path / "chroma")
    for document in load_documents(data_dir):
        store.add_chunks(chunk_document(document))
    return store


# --- SOURCES-line parsing edge cases -------------------------------------


def test_parse_answer_extracts_sources(rag):
    answer, sources = rag.parse_answer("Jeans are allowed.\n\nSOURCES: test-dress-code")
    assert answer == "Jeans are allowed."
    assert sources == ["test-dress-code"]


def test_parse_answer_handles_none_missing_and_case(rag):
    assert rag.parse_answer("Answer.\nSOURCES: none") == ("Answer.", [])
    assert rag.parse_answer("No sources line at all.") == ("No sources line at all.", [])
    assert rag.parse_answer("Answer.\nsources: a, b") == ("Answer.", ["a", "b"])


def test_parse_answer_deduplicates_and_strips(rag):
    _, sources = rag.parse_answer("A.\nSOURCES: a , b,a, ,b")
    assert sources == ["a", "b"]


# --- Scenario 1: fully answerable -----------------------------------------


def test_fully_answerable_question_is_grounded_with_source(rag, store):
    llm = MockLLMClient(
        responses=["Yes — jeans are allowed at headquarters.\nSOURCES: test-dress-code"]
    )
    result = rag.MyRAGPipeline(store, llm).answer("Can I wear jeans at headquarters?")
    assert result.abstained is False
    assert result.sources == ["test-dress-code"]
    assert "jeans" in result.answer.lower()
    assert "SOURCES:" not in result.answer, "the SOURCES line must be split off the answer"
    # The grounded prompt must carry the retrieved evidence and the rules.
    system, user = llm.calls[0]
    assert "ONLY from the context documents" in system.content
    assert "[source: test-dress-code]" in user.content
    assert user.content.rstrip().endswith("Question: Can I wear jeans at headquarters?")


# --- Scenario 2: partially answerable --------------------------------------


def test_partially_answerable_cites_what_exists_and_notes_the_gap(rag, store):
    llm = MockLLMClient(
        responses=[
            "You receive twenty days of paid vacation per year. The provided "
            "documents do not say whether unused days can be sold back.\n"
            "SOURCES: test-vacation"
        ]
    )
    result = rag.MyRAGPipeline(store, llm).answer(
        "How many vacation days do I get, and can I sell unused days back?"
    )
    assert result.abstained is False
    assert result.sources == ["test-vacation"]
    assert "twenty days" in result.answer
    assert "do not say" in result.answer  # the gap is acknowledged, not invented


# --- Scenario 3: unanswerable → abstains without an LLM call ---------------


def test_unanswerable_question_abstains_without_llm_call(rag, store):
    llm = MockLLMClient(responses=["this response must never be used"])
    pipeline = rag.MyRAGPipeline(store, llm, min_score=0.999)  # nothing can pass
    result = pipeline.answer("What is the policy for working from the Moon?")
    assert result.abstained is True
    assert result.answer == ABSTENTION_TEXT
    assert result.sources == []
    assert llm.calls == [], "no chunks retrieved must mean zero LLM calls"


# --- Scenario 4: conflicting retrieved chunks -------------------------------


def test_conflicting_chunks_are_both_supplied_and_acknowledged(rag, store):
    question = "Is there a restocking fee when I return a product that arrived damaged?"
    llm = MockLLMClient(
        responses=[
            "The documents conflict: the standard return policy charges a fifteen "
            "percent restocking fee on opened returns, while damaged products are "
            "refunded in full with no restocking fee.\n"
            "SOURCES: test-returns, test-damaged"
        ]
    )
    pipeline = rag.MyRAGPipeline(store, llm)
    retrieved_ids = {r.chunk.doc_id for r in pipeline.retrieve(question)}
    assert {"test-returns", "test-damaged"} <= retrieved_ids

    result = pipeline.answer(question)
    # Both conflicting documents were passed to the prompt...
    user_content = llm.calls[0][1].content
    assert "[source: test-returns]" in user_content
    assert "[source: test-damaged]" in user_content
    # ...and the (scripted) answer acknowledges the conflict, crediting both.
    assert "conflict" in result.answer.lower()
    assert result.sources == ["test-returns", "test-damaged"]


# --- Scenario 5: low-similarity retrieval below threshold → abstain ---------


def test_low_similarity_retrieval_below_threshold_abstains(rag, store):
    llm = MockLLMClient(responses=["this response must never be used"])
    # An off-topic question only reaches ~0.28 on word overlap; a 0.5 threshold
    # rejects it, so weak coincidental matches never count as evidence.
    pipeline = rag.MyRAGPipeline(store, llm, min_score=0.5)
    result = pipeline.answer("What is the moon made of and who won the world cup?")
    assert result.abstained is True
    assert result.answer == ABSTENTION_TEXT
    assert result.sources == []
    assert llm.calls == []


# --- Scenario 6: a question needing more than one chunk ---------------------


def test_multi_chunk_question_supplies_both_sources_to_the_prompt(rag, store):
    question = (
        "How many days per week can I work remotely, and can I work from another country?"
    )
    llm = MockLLMClient(
        responses=[
            "You may work remotely up to three days per week; working from "
            "another country requires manager approval and is limited to thirty "
            "days per year.\n"
            "SOURCES: test-remote-work, test-international"
        ]
    )
    result = rag.MyRAGPipeline(store, llm).answer(question)
    user_content = llm.calls[0][1].content
    assert "[source: test-remote-work]" in user_content
    assert "[source: test-international]" in user_content
    assert result.abstained is False
    assert result.sources == ["test-remote-work", "test-international"]


# --- Guardrails: hallucinated citations and model-side abstention -----------


def test_hallucinated_source_is_filtered_out(rag, store):
    llm = MockLLMClient(
        responses=["Jeans are allowed.\nSOURCES: test-dress-code, wikipedia-dress-codes"]
    )
    result = rag.MyRAGPipeline(store, llm).answer("Can I wear jeans at headquarters?")
    assert result.sources == ["test-dress-code"], "uncited-context ids must be dropped"


def test_model_side_abstention_is_detected_and_carries_no_sources(rag, store):
    llm = MockLLMClient(responses=[f"{ABSTENTION_TEXT}\nSOURCES: test-dress-code"])
    result = rag.MyRAGPipeline(store, llm).answer("Can I wear jeans at headquarters?")
    assert result.abstained is True
    assert result.sources == [], "an abstention must not credit sources"
