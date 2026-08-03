"""Module 21 tests — reference solution. Always runs, fully offline.

These exercise the production app *through the module's solution re-export*
(``solution/app.py`` -> ``apps.api.main:app``) with FastAPI's ``TestClient``. No
server, no network, no API key. The service's own broader suite lives at
``tests/test_api.py``; this file is the module-local proof that the app wiring a
learner studies is correct.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make the repo-root ``apps`` package importable under pytest's importlib mode.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from techcorp_agent.course_utils import import_from_path  # noqa: E402

MODULE_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def solution():
    return import_from_path("m21_solution_app", MODULE_DIR / "solution" / "app.py")


@pytest.fixture()
def client(solution, tmp_path, monkeypatch):
    """A TestClient forced offline (mock LLM) with a per-test memory DB.

    Offline is set via ``monkeypatch`` (scoped, never leaks) and the cached
    settings are cleared, so the agent builds with the mock LLM inside the
    lifespan handler even on a machine that has a real key in ``.env``.
    """
    from techcorp_agent.config import get_settings

    monkeypatch.setenv("TECHCORP_OFFLINE", "true")
    monkeypatch.setenv("TECHCORP_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    get_settings.cache_clear()
    try:
        with TestClient(solution.app) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()


def test_health_and_ready(client):
    assert client.get("/health").json() == {"status": "ok"}
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json() == {"ready": True}


def test_chat_policy_question_returns_answer_and_conversation_id(client):
    resp = client.post("/chat", json={"question": "What is the remote work policy?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"].strip()
    assert body["route"] == "retrieval"
    assert isinstance(body["sources"], list)
    assert body["conversation_id"]


def test_calculator_question_routes_correctly(client):
    body = client.post("/chat", json={"question": "What is 2 + 2?"}).json()
    assert body["route"] == "calculator"
    assert "4" in body["answer"]


def test_unknown_order_is_safe_not_500(client):
    resp = client.post("/chat", json={"question": "Where is order TC-9999?"})
    assert resp.status_code == 200
    assert "TC-9999" in resp.json()["answer"]


def test_malformed_request_is_422(client):
    assert client.post("/chat", json={}).status_code == 422


def test_streaming_yields_multiple_frames(client):
    resp = client.post("/chat/stream", json={"question": "What is the remote work policy?"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.text.count("data:") > 1
    assert "event: answer" in resp.text


def test_build_agent_is_callable_offline(solution, tmp_path, monkeypatch):
    # The load-once builder must work offline (the mock LLM path).
    from techcorp_agent.config import get_settings

    monkeypatch.setenv("TECHCORP_OFFLINE", "true")
    monkeypatch.setenv("TECHCORP_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    get_settings.cache_clear()
    try:
        agent = solution.build_agent()
        assert agent is not None
    finally:
        get_settings.cache_clear()
