"""Module 11 tests — your starter implementation.

These auto-skip while starter/agent.py still contains TODO markers. Once you
finish the lab they run and become your completion gate:

    uv run pytest course/11_tools_and_routing -q
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.llm.mock_client import MockLLMClient

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/agent.py still contains TODO markers — finish the lab first",
)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m11_starter_agent", STARTER_DIR / "agent.py")


DOC_TEMPLATE = """---
id: {doc_id}
title: {title}
category: test
tags: [test]
---
# {title}

{body}
"""


@pytest.fixture
def store(tmp_path):
    from techcorp_agent.documents.chunking import chunk_document
    from techcorp_agent.documents.loader import load_documents
    from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
    from techcorp_agent.vectorstore.chroma_store import VectorStore

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "test-refunds.md").write_text(
        DOC_TEMPLATE.format(
            doc_id="test-refunds",
            title="Damaged Product Refunds",
            body="Products that arrive damaged receive a full refund within thirty days.",
        ),
        encoding="utf-8",
    )
    store = VectorStore(HashEmbeddingClient(dimension=128), persist_dir=tmp_path / "chroma")
    for doc in load_documents(data_dir):
        store.add_chunks(chunk_document(doc))
    return store


@pytest.fixture
def tools(my_work, store):
    return my_work.build_tools(store)


def test_extract_args_per_tool(my_work):
    assert my_work.extract_args("calculator", "2 + 2") == {"expression": "2 + 2"}
    assert my_work.extract_args("document_search", "refund policy") == {"query": "refund policy"}
    assert my_work.extract_args("order_lookup", "where is TC-1234") == {"order_id": "TC-1234"}
    assert my_work.extract_args("order_lookup", "where is my order") == {}


def test_answer_routes_math_to_calculator(my_work, tools):
    router = MockLLMClient(responses=["calculator"])
    reply = my_work.answer(
        "What is 125 multiplied by 48?", router, MockLLMClient(responses=["x"]), tools
    )
    assert "6000" in reply


def test_answer_unknown_order_is_graceful(my_work, tools):
    router = MockLLMClient(responses=["order_lookup"])
    reply = my_work.answer(
        "status of order TC-9999?", router, MockLLMClient(responses=["x"]), tools
    )
    assert "could not help" in reply


def test_answer_ambiguous_uses_llm(my_work, tools):
    router = MockLLMClient(responses=["none"])
    answer_llm = MockLLMClient(responses=["Which order do you mean?"])
    reply = my_work.answer("Can I return it?", router, answer_llm, tools)
    assert reply == "Which order do you mean?"
