"""Module 14 tests — reference solution. Always runs, fully offline.

Drives the solution's `build_agent` (which delegates to the shared-package
`build_graph` — that equivalence is the module's punchline) through the five
required sample interactions with a hash-embedding store over the real corpus
and scripted mock LLMs. No network, no API key. The deeper cross-cutting suite
(MCP integration, max_loops, bridge) lives in tests/test_capstone.py at the
repo root.
"""

from pathlib import Path

import pytest

from techcorp_agent.capstone.graph import build_graph
from techcorp_agent.course_utils import import_from_path
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT
from techcorp_agent.vectorstore.chroma_store import VectorStore

MODULE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_DIR.parents[1]


@pytest.fixture(scope="module")
def capstone_mod():
    return import_from_path("m14_solution_capstone", MODULE_DIR / "solution" / "capstone.py")


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> VectorStore:
    vs = VectorStore(
        HashEmbeddingClient(dimension=256),
        persist_dir=tmp_path_factory.mktemp("m14_solution_chroma"),
        collection_name="m14_solution",
    )
    for doc in load_documents(REPO_ROOT / "data"):
        vs.add_chunks(chunk_document(doc))
    return vs


def test_policy_question_routes_to_retrieval_and_cites(capstone_mod, store):
    llm = MockLLMClient(
        responses=["document_search", "With approval, yes.\nSOURCES: hr-international-remote"]
    )
    app = capstone_mod.build_agent(llm, store)
    state = capstone_mod.ask(
        app, "Can an international employee work remotely from another country?"
    )
    assert state["route"] == "retrieval"
    assert state["sources"] == ["hr-international-remote"]


def test_denim_question_retrieves_dress_code_when_routed(capstone_mod, store):
    llm = MockLLMClient(responses=["document_search", "Denim is fine.\nSOURCES: hr-dress-code"])
    app = capstone_mod.build_agent(llm, store)
    state = capstone_mod.ask(app, "Am I allowed to wear denim at headquarters?")
    assert state["route"] == "retrieval"
    assert state["sources"] == ["hr-dress-code"]
    assert "hr-dress-code" in state["evidence"]  # retrieval really surfaced it


def test_calculator_returns_1470_without_document_attribution(capstone_mod, store):
    app = capstone_mod.build_agent(MockLLMClient(), store)  # keyword fallback routes math
    state = capstone_mod.ask(app, "What is 17.5% of 8,400?")
    assert state["route"] == "calculator"
    assert "1470" in state["answer"]
    assert state["sources"] == []


def test_order_lookup_known_and_unknown(capstone_mod, store):
    app = capstone_mod.build_agent(MockLLMClient(), store)
    known = capstone_mod.ask(app, "What is happening with order TC-1234?")
    assert known["route"] == "orders"
    assert "in_transit" in known["answer"]

    app = capstone_mod.build_agent(MockLLMClient(), store)
    unknown = capstone_mod.ask(app, "What is happening with order TC-9999?")
    assert unknown["route"] == "orders"
    assert "no order" in unknown["answer"].lower()  # safe message, no crash


def test_moon_question_abstains(capstone_mod, store):
    llm = MockLLMClient(responses=["document_search", f"{ABSTENTION_TEXT}\nSOURCES: none"])
    app = capstone_mod.build_agent(llm, store)
    state = capstone_mod.ask(app, "What is TechCorp's policy for working from the Moon?")
    assert ABSTENTION_TEXT in state["answer"]
    assert state["sources"] == []


def test_solution_matches_library_graph_behavior(capstone_mod, store):
    """The assembled agent and the shared-package graph behave identically."""
    question = "What is 17.5% of 8,400?"
    via_solution = capstone_mod.ask(capstone_mod.build_agent(MockLLMClient(), store), question)
    via_library = build_graph(MockLLMClient(), store).invoke(
        {"conversation_id": "t", "question": question, "trace": [], "loop_count": 0}
    )
    assert via_solution["route"] == via_library["route"]
    assert via_solution["answer"] == via_library["answer"]
    assert via_solution["trace"] == via_library["trace"]


def test_trace_records_router_and_formatter(capstone_mod, store):
    app = capstone_mod.build_agent(MockLLMClient(), store)
    state = capstone_mod.ask(app, "What is 2 + 2?")
    assert any(line.startswith("[node=router]") and "route=" in line for line in state["trace"])
    assert any(line.startswith("[node=formatter]") for line in state["trace"])


def test_main_runs_all_five_interactions_offline(capstone_mod, capsys):
    assert capstone_mod.main() == 0
    out = capsys.readouterr().out
    assert "1) Policy question" in out
    assert "5) Unanswerable" in out
    assert "1470" in out
    assert ABSTENTION_TEXT in out
