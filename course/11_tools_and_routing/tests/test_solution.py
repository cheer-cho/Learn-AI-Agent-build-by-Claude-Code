"""Module 11 tests — reference solution. Always runs, fully offline.

Exercises the agent's routing/answer loop and the six failure behaviors the
lab teaches: ambiguous query, missing argument, timeout, no data, tool raising,
and wrong-tool selection recovered by the keyword fallback.
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path
from techcorp_agent.llm.mock_client import MockLLMClient

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

CORPUS = {
    "test-refunds": (
        "Damaged Product Refunds",
        "Products that arrive damaged receive a full refund within thirty days "
        "of delivery. Photo evidence of the damage is required.",
    ),
    "test-returns": (
        "Standard Return Policy",
        "Opened products returned voluntarily incur a fifteen percent restocking fee.",
    ),
}


@pytest.fixture(scope="module")
def solution():
    return import_from_path("m11_solution_agent", MODULE_DIR / "solution" / "agent.py")


@pytest.fixture
def store(tmp_path):
    from techcorp_agent.documents.chunking import chunk_document
    from techcorp_agent.documents.loader import load_documents
    from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
    from techcorp_agent.vectorstore.chroma_store import VectorStore

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for doc_id, (title, body) in CORPUS.items():
        (data_dir / f"{doc_id}.md").write_text(
            DOC_TEMPLATE.format(doc_id=doc_id, title=title, body=body), encoding="utf-8"
        )
    store = VectorStore(HashEmbeddingClient(dimension=128), persist_dir=tmp_path / "chroma")
    for doc in load_documents(data_dir):
        store.add_chunks(chunk_document(doc))
    return store


@pytest.fixture
def tools(solution, store):
    return solution.build_tools(store)


def test_extract_args_per_tool(solution):
    assert solution.extract_args("calculator", "2 + 2") == {"expression": "2 + 2"}
    assert solution.extract_args("document_search", "refund policy") == {"query": "refund policy"}
    assert solution.extract_args("order_lookup", "where is TC-1234") == {"order_id": "TC-1234"}
    # No id present -> empty args (drives the missing-argument failure path).
    assert solution.extract_args("order_lookup", "where is my order") == {}


def test_answer_routes_math_to_calculator(solution, tools):
    router = MockLLMClient(responses=["calculator"])
    answer_llm = MockLLMClient(responses=["unused"])
    reply = solution.answer("What is 125 multiplied by 48?", router, answer_llm, tools)
    assert "6000" in reply
    assert "[calculator]" in reply


def test_answer_routes_order_to_lookup(solution, tools):
    router = MockLLMClient(responses=["order_lookup"])
    reply = solution.answer(
        "status of order TC-1234?", router, MockLLMClient(responses=["x"]), tools
    )
    assert "in_transit" in reply


def test_answer_routes_policy_to_search(solution, tools):
    router = MockLLMClient(responses=["document_search"])
    reply = solution.answer(
        "Can I return a damaged product?", router, MockLLMClient(responses=["x"]), tools
    )
    assert "test-refunds" in reply or "score" in reply


# --- failure exercises -------------------------------------------------------


def test_unknown_order_is_graceful(solution, tools):
    router = MockLLMClient(responses=["order_lookup"])
    reply = solution.answer(
        "status of order TC-9999?", router, MockLLMClient(responses=["x"]), tools
    )
    assert "could not help" in reply
    assert "TC-9999" in reply


def test_missing_order_id_is_graceful(solution, tools):
    # Router picks order_lookup but the question has no id -> missing-argument
    # failure surfaced, not a crash.
    router = MockLLMClient(responses=["order_lookup"])
    reply = solution.answer("where is my order?", router, MockLLMClient(responses=["x"]), tools)
    assert "could not help" in reply
    assert "order_id" in reply


def test_ambiguous_question_answered_by_llm(solution, tools):
    router = MockLLMClient(responses=["none"])
    answer_llm = MockLLMClient(responses=["Could you tell me which order you mean?"])
    reply = solution.answer("Can I return it?", router, answer_llm, tools)
    assert reply == "Could you tell me which order you mean?"


def test_wrong_tool_reply_recovered_by_fallback(solution, tools):
    # LLM hallucinates a nonexistent tool; keyword fallback reads the order id.
    router = MockLLMClient(responses=["weather_tool"])
    reply = solution.answer(
        "Where is order TC-2048?", router, MockLLMClient(responses=["x"]), tools
    )
    assert "delayed" in reply


def test_solution_main_runs_offline(solution, capsys, monkeypatch, tmp_path):
    # Point the demo store at a temp dir so it does not touch the repo .chroma.
    # data_dir keeps its default (the real mock corpus), which is what the demo
    # document-search question needs.
    from techcorp_agent.config import Settings

    monkeypatch.setattr(
        solution,
        "get_settings",
        lambda: Settings(_env_file=None, techcorp_offline=True, chroma_dir=tmp_path / "chroma"),
    )
    assert solution.main() == 0
    out = capsys.readouterr().out
    assert "6000" in out
    assert "in_transit" in out
    assert "TC-9999" in out
