"""Module 18 tests — your starter implementation.

These auto-skip while starter/multi_agent_lab.py still contains TODO markers.
Once you finish the lab, they run and become your completion gate:

    uv run pytest course/18_multi_agent -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techcorp_agent.agents import SupervisorAgent
from techcorp_agent.agents.comparison import RunOutcome
from techcorp_agent.course_utils import import_from_path, starter_incomplete

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/multi_agent_lab.py still contains TODO markers — finish the lab first",
)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m18_starter_multi_agent_lab", STARTER_DIR / "multi_agent_lab.py")


@pytest.fixture(scope="module")
def store(my_work):
    return my_work.build_offline_store()


def test_build_supervisor_returns_a_supervisor(my_work, store):
    supervisor = my_work.build_supervisor(store)
    assert isinstance(supervisor, SupervisorAgent)


def test_single_agent_fn_returns_run_outcome(my_work, store):
    fn = my_work.single_agent_fn(store)
    outcome = fn("How many vacation days do employees get each year?")
    assert isinstance(outcome, RunOutcome)
    # The single agent made at least one LLM call (its router runs every time).
    assert outcome.llm_calls >= 1
    assert isinstance(outcome.answer, str) and outcome.answer.strip()


def test_supervisor_routes_and_answers(my_work, store):
    supervisor = my_work.build_supervisor(store)
    supervisor.answer("Where is my order TC-1234?")
    assert supervisor.last_specialist == "orders"


def test_main_runs_offline(my_work, monkeypatch):
    monkeypatch.setenv("TECHCORP_OFFLINE", "true")
    assert my_work.main() == 0
