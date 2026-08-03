"""Module 14 capstone tests — the TechCorp Knowledge Agent v1 graph.

Fully offline and deterministic: a hash-embedding vector store built from the
*real* ``data/`` corpus, plus a scripted ``MockLLMClient`` so both the router
decision and the grounded answer are exact. No API key, no network.

These tests cover the spec's five required sample interactions plus the
cross-cutting guarantees (trace records the router decision, max_loops is
enforced, the MCP-unavailable fallback works, and the formatter output shape is
consistent). One integration test drives the real MCP registry through the
:class:`SyncMCPRegistry` bridge; the other order tests use the local fallback.

Router/answer call order per graph invoke:
- the router node makes ONE LLM call (``route_question``), then
- the retrieval node makes ONE more (the grounded answer), while the
  calculator/orders nodes make none and the general node makes one.
So a scripted client for a retrieval turn needs ``[router_reply, answer_reply]``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from techcorp_agent.capstone import build_graph, build_offline_store
from techcorp_agent.capstone.graph import (
    ROUTE_CALCULATOR,
    ROUTE_GENERAL,
    ROUTE_ORDERS,
    ROUTE_RETRIEVAL,
)
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT
from techcorp_agent.vectorstore.chroma_store import VectorStore

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"


# -- fixtures ---------------------------------------------------------------


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> VectorStore:
    """A hash-embedding store indexed from the real TechCorp corpus (offline)."""
    persist = tmp_path_factory.mktemp("capstone_chroma")
    vs = VectorStore(
        HashEmbeddingClient(dimension=256),
        persist_dir=persist,
        collection_name="capstone_test",
    )
    for doc in load_documents(DATA_DIR):
        vs.add_chunks(chunk_document(doc))
    return vs


def _invoke(app, question: str) -> dict:
    return app.invoke(
        {
            "conversation_id": "test",
            "question": question,
            "trace": [],
            "loop_count": 0,
        }
    )


# -- 1) policy question -> retrieval, cites hr-international-remote ----------


def test_international_remote_routes_to_retrieval_and_cites_source(store):
    llm = MockLLMClient(
        responses=[
            "document_search",  # router decision
            "International employees may work remotely from another country with "
            "manager approval and up to the annual limit.\nSOURCES: hr-international-remote",
        ]
    )
    app = build_graph(llm, store)
    state = _invoke(app, "Can an international employee work remotely from another country?")

    assert state["route"] == ROUTE_RETRIEVAL
    assert state["sources"] == ["hr-international-remote"]
    assert "hr-international-remote" in state["sources"]
    assert not state["answer"].startswith(ABSTENTION_TEXT)


# -- 2) semantic wording difference: denim/jeans -> dress code --------------


def test_jeans_phrasing_retrieves_dress_code(store):
    """The keyword router routes a 'jeans ... dress code' question to retrieval,
    and hash retrieval finds hr-dress-code."""
    llm = MockLLMClient(
        responses=[
            "document_search",
            "Yes, jeans are acceptable under the business-casual dress code at "
            "headquarters.\nSOURCES: hr-dress-code",
        ]
    )
    app = build_graph(llm, store)
    state = _invoke(app, "Am I allowed to wear jeans under the dress code at headquarters?")

    assert state["route"] == ROUTE_RETRIEVAL
    assert state["sources"] == ["hr-dress-code"]


def test_denim_phrasing_still_retrieves_dress_code_when_routed(store):
    """Documented semantic-difference case: 'denim' shares no keyword with the
    dress-code policy, so offline the keyword router does NOT send it to
    retrieval — but WHEN routed there (real LLM router, or scripted here), hash
    retrieval still surfaces hr-dress-code because 'wear'/'headquarters' overlap.
    """
    # Confirm the store can retrieve dress-code from the denim phrasing.
    retrieved = store.query("Am I allowed to wear denim at headquarters?", top_k=4, min_score=0.05)
    assert retrieved and retrieved[0].chunk.doc_id == "hr-dress-code"

    llm = MockLLMClient(
        responses=[
            "document_search",  # a real LLM router picks this from intent
            "Denim is fine under the business-casual dress code.\nSOURCES: hr-dress-code",
        ]
    )
    app = build_graph(llm, store)
    state = _invoke(app, "Am I allowed to wear denim at headquarters?")
    assert state["route"] == ROUTE_RETRIEVAL
    assert state["sources"] == ["hr-dress-code"]


@pytest.mark.live
def test_denim_phrasing_routes_via_real_llm():
    """With a real LLM router, the denim phrasing routes to retrieval on intent
    alone (no keyword overlap). Requires a real key; skipped offline."""
    from techcorp_agent.config import get_settings
    from techcorp_agent.llm.factory import get_llm_client

    settings = get_settings()
    llm = get_llm_client(settings)
    live_store = build_offline_store()
    app = build_graph(llm, live_store)
    state = _invoke(app, "Am I allowed to wear denim at headquarters?")
    assert state["route"] == ROUTE_RETRIEVAL


# -- 3) calculator -> 1470, NOT attributed to documents ---------------------


def test_percentage_calculation_routes_to_calculator_and_omits_sources(store):
    # Math routes deterministically via the keyword fallback, so any router
    # reply works; the calculator node runs the local tool (no MCP here).
    llm = MockLLMClient()
    app = build_graph(llm, store)
    state = _invoke(app, "What is 17.5% of 8,400?")

    assert state["route"] == ROUTE_CALCULATOR
    assert "1470" in state["answer"]
    # The formatter must NOT pretend this came from documents.
    assert state["sources"] == []
    assert "source" not in state["answer"].lower()


# -- 4) order lookup --------------------------------------------------------


def test_order_lookup_local_fallback_known_order(store):
    llm = MockLLMClient()
    app = build_graph(llm, store)  # no MCP -> local order tool
    state = _invoke(app, "What is happening with order TC-1234?")

    assert state["route"] == ROUTE_ORDERS
    assert "TC-1234" in state["answer"]
    assert "in_transit" in state["answer"]
    assert state["sources"] == []


def test_unknown_order_returns_safe_message(store):
    llm = MockLLMClient()
    app = build_graph(llm, store)
    state = _invoke(app, "What is happening with order TC-9999?")

    assert state["route"] == ROUTE_ORDERS
    assert "TC-9999" in state["answer"]
    assert "no order" in state["answer"].lower()
    # A safe message, never a crash and never fake sources.
    assert state["sources"] == []


@pytest.mark.skipif(sys.platform == "win32", reason="stdio MCP servers are POSIX-oriented here")
def test_order_lookup_via_real_mcp_registry(store):
    """Integration: drive the order route through the real MCP servers via the
    synchronous bridge. Confirms MCP tools are discoverable and callable."""
    from techcorp_agent.capstone.mcp_bridge import SyncMCPRegistry

    registry = SyncMCPRegistry.connect()
    assert registry is not None, "MCP servers failed to spawn"
    try:
        assert "orders.get_order_status" in registry.tools()
        llm = MockLLMClient()
        app = build_graph(llm, store, mcp_registry=registry)
        state = _invoke(app, "What is happening with order TC-1234?")
        assert state["route"] == ROUTE_ORDERS
        assert "TC-1234" in state["answer"]
        assert "in_transit" in state["answer"]
        # Trace shows the MCP backend was used, not the local fallback.
        assert any("backend=mcp" in line for line in state["trace"])
    finally:
        registry.close()


# -- 5) unanswerable -> abstention ------------------------------------------


def test_moon_question_abstains(store):
    """Out-of-scope question: retrieval returns weak/irrelevant chunks, and the
    grounded prompt makes the model abstain. The pipeline detects the abstention
    text and drops any sources."""
    llm = MockLLMClient(
        responses=[
            "document_search",  # router still sends it to retrieval
            f"{ABSTENTION_TEXT}\nSOURCES: none",
        ]
    )
    app = build_graph(llm, store)
    state = _invoke(app, "What is TechCorp's policy for working from the Moon?")

    assert state["route"] == ROUTE_RETRIEVAL
    assert ABSTENTION_TEXT in state["answer"]
    assert state["sources"] == []


# -- cross-cutting guarantees ----------------------------------------------


def test_trace_records_router_decision(store):
    llm = MockLLMClient()
    app = build_graph(llm, store)
    state = _invoke(app, "What is 2 + 2?")
    router_lines = [line for line in state["trace"] if line.startswith("[node=router]")]
    assert router_lines and "route=" in router_lines[0]
    # Every route also passes through the formatter node.
    assert any(line.startswith("[node=formatter]") for line in state["trace"])


def test_max_loops_is_enforced_on_retrieval(store):
    """Even if the grounded answer is empty on every pass, the retrieval retry
    edge can never push loop_count past max_loops."""
    # Router picks retrieval, then every grounded answer is empty -> retry until
    # the cap. Provide enough empty answers to exceed the cap if it were not
    # enforced; the cap must stop it at max_loops.
    responses = ["document_search"] + [""] * 10
    llm = MockLLMClient(responses=responses)
    app = build_graph(llm, store, max_loops=2)
    state = _invoke(app, "What is the remote work policy?")
    assert state["loop_count"] <= 2


def test_no_mcp_fallback_answers_calculator_and_orders(store):
    """The --no-mcp path (mcp_registry=None) answers math and order questions
    with local tools, no crash."""
    app = build_graph(MockLLMClient(), store, mcp_registry=None)
    calc = _invoke(app, "What is 6 * 7?")
    assert "42" in calc["answer"]
    order = build_graph(MockLLMClient(), store, mcp_registry=None)
    order_state = _invoke(order, "Where is order TC-2048?")
    assert "TC-2048" in order_state["answer"]


def test_formatter_output_shape_is_consistent(store):
    """Every route yields a non-empty string answer and a list of sources; only
    the retrieval route may carry sources."""
    cases = [
        (
            MockLLMClient(responses=["document_search", "Answer.\nSOURCES: hr-remote-work"]),
            "What is the remote work policy?",
            ROUTE_RETRIEVAL,
            True,
        ),
        (MockLLMClient(), "What is 3 + 4?", ROUTE_CALCULATOR, False),
        (MockLLMClient(), "Where is order TC-1234?", ROUTE_ORDERS, False),
        (MockLLMClient(), "Hello there, thanks!", ROUTE_GENERAL, False),
    ]
    for llm, question, expected_route, may_have_sources in cases:
        app = build_graph(llm, store)
        state = _invoke(app, question)
        assert state["route"] == expected_route
        assert isinstance(state["answer"], str) and state["answer"].strip()
        assert isinstance(state["sources"], list)
        if not may_have_sources:
            assert state["sources"] == []
