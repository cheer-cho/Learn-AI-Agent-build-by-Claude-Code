"""Module 21 tests — your starter implementation (the completion gate).

These auto-skip while ``starter/app.py`` still contains TODO markers. Once you
finish the lab, they run against *your* app object and become your gate:

    uv run pytest course/21_production_deployment -q

Everything is offline (mock LLM), in-process (FastAPI ``TestClient``), and needs
no server, network, or API key.
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

from techcorp_agent.course_utils import import_from_path, starter_incomplete  # noqa: E402

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/app.py still contains TODO markers — finish the lab first",
)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m21_starter_app", STARTER_DIR / "app.py")


@pytest.fixture()
def client(my_work, tmp_path, monkeypatch):
    """A TestClient forced offline (mock LLM) with a per-test memory DB.

    Offline is set via ``monkeypatch`` (scoped, never leaks) and the settings
    cache is cleared, so the mock LLM is used even if a real key sits in ``.env``.
    """
    from techcorp_agent.config import get_settings

    monkeypatch.setenv("TECHCORP_OFFLINE", "true")
    monkeypatch.setenv("TECHCORP_MEMORY_DB", str(tmp_path / "memory.sqlite3"))
    get_settings.cache_clear()
    try:
        with TestClient(my_work.app) as test_client:
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


def test_empty_question_is_400(client):
    resp = client.post("/chat", json={"question": "   "})
    assert resp.status_code == 400
