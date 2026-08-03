"""Offline tests for the production FastAPI service (Module 21).

Everything here runs with FastAPI's ``TestClient`` against the in-process app —
no real server, no network, no API key. The ``TestClient`` context manager
(``with TestClient(app) as client``) is load-bearing: entering it runs the
lifespan handler, which is what builds the index + agent once and flips
``/ready`` to ``200``. Outside that block the app is *not* ready — which is the
whole point of a readiness probe.

The suite proves the Module 21 acceptance behaviors:

- ``/health`` and ``/ready`` report ok;
- ``POST /chat`` on a policy question returns an answer + sources + conversation id;
- a calculator question routes to the calculator;
- an unknown order (``TC-9999``) is a safe message, not a 500;
- a malformed request (missing ``question``) is a clean 422, not a crash;
- conversation continuity: a second turn on the same id sees the first;
- the streaming endpoint yields multiple SSE frames;
- an unavailable MCP server does not crash the endpoint (the app never spawns
  MCP servers — it uses the local-tool fallback — so this is the default path).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# The service lives in ``apps/`` at the repo root, which is not an installed
# package (only ``src/techcorp_agent`` is). Put the repo root on the path so
# ``import apps.api.main`` resolves under pytest's importlib mode.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.api.main import app  # noqa: E402 - after the repo root is on the path


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient forced offline, with a memory DB isolated per test.

    The agent is built inside the ``TestClient`` context (the lifespan handler),
    so setting ``TECHCORP_OFFLINE`` here — and clearing the cached settings —
    guarantees the mock LLM even on a machine with a real key in ``.env``. We use
    ``monkeypatch`` (not a module-level ``os.environ`` write) so the override is
    scoped to the test and never leaks into, e.g., ``test_config.py``. Pointing
    ``TECHCORP_MEMORY_DB`` at a tmp file keeps conversation threads from leaking
    across tests and exercises the production volume-path override.
    """
    from techcorp_agent.config import get_settings

    monkeypatch.setenv("TECHCORP_OFFLINE", "true")
    monkeypatch.setenv("TECHCORP_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    get_settings.cache_clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()


def test_health_reports_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_reports_ready_once_index_loaded(client):
    # Inside the TestClient context the lifespan handler has run, so we are ready.
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"ready": True}


def test_chat_policy_question_returns_answer_sources_and_conversation_id(client):
    resp = client.post("/chat", json={"question": "What is the remote work policy?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"].strip(), "a policy question must yield a non-empty answer"
    assert body["route"] == "retrieval", "a policy question routes to grounded retrieval"
    assert isinstance(body["sources"], list), "sources must always be present as a list"
    assert body["conversation_id"], "every answer carries a conversation id"


def test_chat_calculator_question_routes_correctly(client):
    resp = client.post("/chat", json={"question": "What is 2 + 2?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["route"] == "calculator"
    assert "4" in body["answer"]


def test_unknown_order_returns_safe_message_not_500(client):
    resp = client.post("/chat", json={"question": "Where is order TC-9999?"})
    assert resp.status_code == 200, "an unknown order must degrade, never 500"
    body = resp.json()
    assert body["route"] == "orders"
    assert "TC-9999" in body["answer"], "the safe message names the order it could not find"
    assert body["sources"] == [], "an order lookup is never dressed up with document sources"


def test_malformed_request_missing_question_is_422_not_a_crash(client):
    resp = client.post("/chat", json={})
    assert resp.status_code == 422, "a missing question is a clean validation error"
    detail = resp.json().get("detail")
    assert detail, "422 carries a structured 'detail' explaining the missing field"
    assert any("question" in str(item).lower() for item in detail)


def test_empty_question_is_rejected_with_a_clear_400(client):
    resp = client.post("/chat", json={"question": "   "})
    assert resp.status_code == 400
    assert "empty" in resp.json()["error"].lower()


def test_conversation_id_continuity_across_two_posts(client):
    first = client.post("/chat", json={"question": "My name is Dana."})
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/chat",
        json={"question": "What did I just say?", "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id

    # The checkpointer threads history by conversation id: after two turns the
    # persisted thread holds both user turns (and both assistant replies), which
    # is what makes the second turn able to see the first.
    snapshot = app.state.agent.get_state({"configurable": {"thread_id": conversation_id}})
    messages = snapshot.values.get("messages", [])
    user_turns = [m for m in messages if getattr(m, "role", None) == "user"]
    assert len(user_turns) == 2, "the second turn's thread includes the first turn"
    assert user_turns[0].content == "My name is Dana."


def test_streaming_endpoint_yields_multiple_sse_chunks(client):
    resp = client.post("/chat/stream", json={"question": "What is the remote work policy?"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    frames = [line for line in resp.text.splitlines() if line.startswith("data:")]
    assert len(frames) > 1, "the stream emits several SSE frames as the graph runs"
    # The final frame carries the grounded answer.
    assert "answer" in resp.text
    assert "event: answer" in resp.text


def test_streaming_malformed_request_is_422_before_streaming(client):
    # A missing question fails Pydantic validation before the stream even starts.
    resp = client.post("/chat/stream", json={})
    assert resp.status_code == 422


def test_unavailable_mcp_server_does_not_crash_the_endpoint(client):
    """The service never spawns MCP servers; math/order questions use local tools.

    This is the ``--no-mcp`` equivalent: because the app builds the graph with no
    MCP registry, a math or order question is answered by the in-process local
    tools and can never crash on an unavailable MCP server.
    """
    calc = client.post("/chat", json={"question": "What is 10 * 5?"})
    assert calc.status_code == 200
    assert "50" in calc.json()["answer"]

    order = client.post("/chat", json={"question": "Status of order TC-1001?"})
    assert order.status_code == 200
    assert order.json()["route"] == "orders"


def test_metrics_counts_conversations_and_turns(client):
    client.post("/chat", json={"question": "hello"})
    client.post("/chat", json={"question": "hello again"})
    metrics = client.get("/metrics").json()
    assert metrics["conversations"] >= 1
    assert metrics["total_turns"] >= 2
