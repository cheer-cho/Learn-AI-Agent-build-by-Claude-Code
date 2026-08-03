"""Module 22 tests — reference solution. Always runs, fully offline.

Drives the solution's `build_agent` (which delegates to the shared-package
`build_v2_graph` — that equivalence is the module's punchline) through the
integrated capabilities with a hash-embedding store over the real corpus, a tmp
sqlite checkpointer, and scripted mock LLMs. No network, no API key. The deeper
cross-cutting suite lives in `tests/test_capstone_v2.py` at the repo root.
"""

from pathlib import Path

import pytest

from techcorp_agent.capstone_v2 import build_v2_graph
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
    return import_from_path("m22_solution_capstone", MODULE_DIR / "solution" / "capstone_v2.py")


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> VectorStore:
    vs = VectorStore(
        HashEmbeddingClient(dimension=256),
        persist_dir=tmp_path_factory.mktemp("m22_solution_chroma"),
        collection_name="m22_solution",
    )
    for doc in load_documents(REPO_ROOT / "data"):
        vs.add_chunks(chunk_document(doc))
    return vs


def _db(tmp_path):
    return tmp_path / "mem.sqlite"


def test_policy_routes_to_specialist_and_cites(capstone_mod, store, tmp_path):
    llm = MockLLMClient(
        responses=["policy", "With approval, yes.\nSOURCES: hr-international-remote"]
    )
    app = capstone_mod.build_agent(llm, store, db_path=_db(tmp_path))
    state = capstone_mod.ask(app, "Can an international employee work remotely?", "c1")
    assert state["route"] == "policy"
    assert state["sources"] == ["hr-international-remote"]


def test_calculator_1470_without_document_attribution(capstone_mod, store, tmp_path):
    app = capstone_mod.build_agent(MockLLMClient(), store, db_path=_db(tmp_path))
    state = capstone_mod.ask(app, "What is 17.5% of 8,400?", "c2")
    assert state["route"] == "calculator"
    assert "1470" in state["answer"]
    assert state["sources"] == []


def test_order_lookup_known_and_unknown(capstone_mod, store, tmp_path):
    app = capstone_mod.build_agent(MockLLMClient(), store, db_path=_db(tmp_path))
    known = capstone_mod.ask(app, "What is happening with order TC-1234?", "c3")
    assert known["route"] == "orders"
    assert "in_transit" in known["answer"]

    unknown = capstone_mod.ask(app, "What is happening with order TC-9999?", "c4")
    assert "no order" in unknown["answer"].lower()


def test_moon_abstains(capstone_mod, store, tmp_path):
    llm = MockLLMClient(responses=["policy", f"{ABSTENTION_TEXT}\nSOURCES: none"])
    app = capstone_mod.build_agent(llm, store, db_path=_db(tmp_path))
    state = capstone_mod.ask(app, "What is TechCorp's policy for working from the Moon?", "c5")
    assert ABSTENTION_TEXT in state["answer"]
    assert state["sources"] == []


def test_solution_matches_library_graph_behavior(capstone_mod, store, tmp_path):
    """The assembled agent and the shared-package graph behave identically."""
    question = "What is 17.5% of 8,400?"
    via_solution = capstone_mod.ask(
        capstone_mod.build_agent(MockLLMClient(), store, db_path=_db(tmp_path)), question, "s"
    )
    via_library = build_v2_graph(MockLLMClient(), store, db_path=tmp_path / "lib.sqlite").invoke(
        {"question": question, "trace": []}, {"configurable": {"thread_id": "l"}}
    )
    assert via_solution["route"] == via_library["route"]
    assert via_solution["answer"] == via_library["answer"]


def test_main_runs_all_capabilities_offline(capstone_mod, capsys):
    assert capstone_mod.main() == 0
    out = capsys.readouterr().out
    assert "1) Policy" in out
    assert "1470" in out
    assert "Approval gate" in out or "Approval" in out
    assert ABSTENTION_TEXT in out
    assert "Injection defense" in out
    assert "All v2 capabilities ran offline." in out
