"""Module 14 tests — your starter assembly.

Auto-skips while `starter/` still contains TODO markers; once you finish the
lab it runs and becomes your completion gate:

    uv run pytest course/14_capstone_v1 -q

It drives YOUR `build_agent` through the five required sample interactions and
checks the same invariants the reference satisfies: routing, citation,
calculator honesty, safe order handling, abstention, and the trace. Fully
offline.
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT
from techcorp_agent.vectorstore.chroma_store import VectorStore

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"
REPO_ROOT = MODULE_DIR.parents[1]

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/ still contains TODO markers — finish the lab first",
)


@pytest.fixture(scope="module")
def capstone_mod():
    return import_from_path("m14_starter_capstone", STARTER_DIR / "capstone.py")


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> VectorStore:
    vs = VectorStore(
        HashEmbeddingClient(dimension=256),
        persist_dir=tmp_path_factory.mktemp("m14_starter_chroma"),
        collection_name="m14_starter",
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


def test_calculator_returns_1470_without_document_attribution(capstone_mod, store):
    app = capstone_mod.build_agent(MockLLMClient(), store)
    state = capstone_mod.ask(app, "What is 17.5% of 8,400?")
    assert state["route"] == "calculator"
    assert "1470" in state["answer"]
    # Your formatter must never dress a computed number up as a document answer.
    assert state["sources"] == []


def test_order_lookup_known_and_unknown(capstone_mod, store):
    app = capstone_mod.build_agent(MockLLMClient(), store)
    known = capstone_mod.ask(app, "What is happening with order TC-1234?")
    assert known["route"] == "orders"
    assert "in_transit" in known["answer"]

    app = capstone_mod.build_agent(MockLLMClient(), store)
    unknown = capstone_mod.ask(app, "What is happening with order TC-9999?")
    assert "no order" in unknown["answer"].lower()  # safe message, never a crash


def test_moon_question_abstains(capstone_mod, store):
    llm = MockLLMClient(responses=["document_search", f"{ABSTENTION_TEXT}\nSOURCES: none"])
    app = capstone_mod.build_agent(llm, store)
    state = capstone_mod.ask(app, "What is TechCorp's policy for working from the Moon?")
    assert ABSTENTION_TEXT in state["answer"]
    assert state["sources"] == []


def test_general_route_and_trace(capstone_mod, store):
    app = capstone_mod.build_agent(MockLLMClient(), store)
    state = capstone_mod.ask(app, "Hi there, thanks for the help!")
    assert state["route"] == "general"
    assert state["sources"] == []
    assert any(line.startswith("[node=router]") for line in state["trace"])
    assert any(line.startswith("[node=formatter]") for line in state["trace"])
