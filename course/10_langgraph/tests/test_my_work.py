"""Module 10 tests — your starter implementation.

These auto-skip while starter/graphs.py still contains TODO markers. Once you
finish the labs they run and become your completion gate:

    uv run pytest course/10_langgraph -q
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.llm.mock_client import MockLLMClient

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/graphs.py still contains TODO markers — finish the labs first",
)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m10_starter_graphs", STARTER_DIR / "graphs.py")


def test_lab_a_final_state(my_work):
    app = my_work.build_lab_a()
    final = app.invoke({"name": "Dana", "message": "", "status": "pending", "trace": []})
    assert final["message"] == "Hello, Dana! Welcome to TechCorp."
    assert final["status"] == "complete"


def test_lab_b_stage_order(my_work):
    client = MockLLMClient(responses=["OUTLINE", "DRAFT", "REVIEW", "FINAL"])
    app = my_work.make_draft_graph(client)
    final = app.invoke(
        {
            "topic": "T",
            "outline": "",
            "draft": "",
            "review": "",
            "final": "",
            "status": "pending",
            "trace": [],
        }
    )
    stages = [line.split("]")[0].replace("[node=", "") for line in final["trace"]]
    assert stages == ["outline", "draft", "review", "finalize"]
    assert final["final"] == "FINAL"
    assert final["status"] == "finalized"


def test_lab_c_routes_both_ways(my_work):
    assert my_work.run_lab_c("What are the office hours?")["route"] == "short"
    assert my_work.run_lab_c("Analyze our GDPR policy gaps.")["route"] == "detailed"


def test_lab_d_stops_at_cap(my_work):
    final = my_work.run_lab_d([0.1, 0.1, 0.1, 0.1, 0.1])
    assert final["iteration"] == my_work.MAX_ITERATIONS
    assert final["status"] == "max_iterations_reached"


def test_lab_d_exits_early(my_work):
    final = my_work.run_lab_d([0.4, 0.9])
    assert final["iteration"] == 2
    assert final["status"] == "sufficient_evidence"
