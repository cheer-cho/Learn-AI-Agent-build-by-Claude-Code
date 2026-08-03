"""Module 22 tests — your starter assembly.

Auto-skips while `starter/` still contains TODO markers; once you finish the lab
it runs and becomes your completion gate:

    uv run pytest course/22_hero_capstone -q

It drives YOUR integration helpers through the five joints — build-with-memory,
the approval interrupt, the safety budget, tracing, and streaming — and checks
the same invariants the reference satisfies. Fully offline.
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.tracing import LocalTracer
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
    return import_from_path("m22_starter_capstone", STARTER_DIR / "capstone_v2.py")


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> VectorStore:
    vs = VectorStore(
        HashEmbeddingClient(dimension=256),
        persist_dir=tmp_path_factory.mktemp("m22_starter_chroma"),
        collection_name="m22_starter",
    )
    for doc in load_documents(REPO_ROOT / "data"):
        vs.add_chunks(chunk_document(doc))
    return vs


def _db(tmp_path):
    return tmp_path / "mem.sqlite"


def test_build_and_ask_policy_cites(capstone_mod, store, tmp_path):
    llm = MockLLMClient(
        responses=["policy", "With approval, yes.\nSOURCES: hr-international-remote"]
    )
    app = capstone_mod.build_agent(llm, store, db_path=_db(tmp_path))
    state = capstone_mod.ask(app, "Can an international employee work remotely?", "c1")
    assert state["route"] == "policy"
    assert state["sources"] == ["hr-international-remote"]


def test_calculator_1470(capstone_mod, store, tmp_path):
    app = capstone_mod.build_agent(MockLLMClient(), store, db_path=_db(tmp_path))
    state = capstone_mod.ask(app, "What is 17.5% of 8,400?", "c2")
    assert state["route"] == "calculator"
    assert "1470" in state["answer"]
    assert state["sources"] == []


def test_memory_survives_new_graph(capstone_mod, store, tmp_path):
    db = _db(tmp_path)
    llm1 = MockLLMClient(responses=["policy", "Up to 30 days.\nSOURCES: hr-international-remote"])
    g1 = capstone_mod.build_agent(llm1, store, db_path=db)
    capstone_mod.ask(g1, "Can I work remotely from another country?", "conv")
    llm2 = MockLLMClient(
        responses=["policy", "Longer stays need approval.\nSOURCES: hr-international-remote"]
    )
    g2 = capstone_mod.build_agent(llm2, store, db_path=db)
    capstone_mod.ask(g2, "What does the remote policy say about longer stays?", "conv")
    assert any("Conversation so far" in m.content for c in llm2.calls for m in c)


def test_approval_interrupt_approve_and_reject(capstone_mod, store, tmp_path):
    g = capstone_mod.build_agent(MockLLMClient(), store, db_path=_db(tmp_path))
    approved = capstone_mod.approve_ticket(
        g, "Please open a support ticket for order TC-2048", "tk-a", approved=True
    )
    assert "Created support ticket" in approved["answer"]

    g2 = capstone_mod.build_agent(MockLLMClient(), store, db_path=tmp_path / "b.sqlite")
    rejected = capstone_mod.approve_ticket(
        g2, "Please file a support ticket for order TC-2048", "tk-r", approved=False
    )
    assert "No ticket was created" in rejected["answer"]


def test_budget_hard_limit_blocks(capstone_mod, store, tmp_path):
    from techcorp_agent.safety.budget import SessionBudget

    g = capstone_mod.build_agent(
        MockLLMClient(),
        store,
        db_path=_db(tmp_path),
        budget=SessionBudget(soft_limit_usd=0.0, hard_limit_usd=0.0),
    )
    state = capstone_mod.ask(g, "How much vacation do I get?", "bud")
    assert state.get("blocked") is True


def test_tracing_captures_run(capstone_mod, store, tmp_path):
    trace_path = tmp_path / "runs.jsonl"
    tracer = LocalTracer(path=trace_path)
    llm = MockLLMClient()
    g = capstone_mod.build_agent(llm, store, db_path=_db(tmp_path))
    state = capstone_mod.traced_run(g, "What is 2+2?", "tr", tracer, llm)
    assert "4" in state["answer"]
    assert trace_path.exists() and trace_path.stat().st_size > 0


def test_streaming_yields_events(capstone_mod, store, tmp_path):
    g = capstone_mod.build_agent(MockLLMClient(), store, db_path=_db(tmp_path))
    events = capstone_mod.stream_run(g, "What is 2+2?", "st")
    assert len(events) >= 3


def test_main_runs_offline(capstone_mod, capsys):
    assert capstone_mod.main() == 0
    out = capsys.readouterr().out
    assert "All integrated capabilities ran offline." in out
