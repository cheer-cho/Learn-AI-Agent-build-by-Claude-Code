"""Module 10 tests — reference solution. Always runs, fully offline.

Covers all four labs, including the two behaviors the spec insists on for the
loop: it stops at the max-iteration cap when evidence never improves (proving
it cannot run forever) and exits early when evidence clears the threshold.
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path
from techcorp_agent.llm.mock_client import MockLLMClient

MODULE_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def solution():
    return import_from_path("m10_solution_graphs", MODULE_DIR / "solution" / "graphs.py")


# --- Lab A: basic graph produces the expected final state ------------------


def test_lab_a_final_state(solution):
    app = solution.build_lab_a()
    final = app.invoke({"name": "Dana", "message": "", "status": "pending", "trace": []})
    assert final["message"] == "Hello, Dana! Welcome to TechCorp."
    assert final["status"] == "complete"
    assert final["trace"] == [
        "[node=greeting] message='Hello, Dana!'",
        "[node=enhancement] message='Hello, Dana! Welcome to TechCorp.'",
    ]


# --- Lab B: passes through all four stages in order ------------------------


def test_lab_b_stage_order_and_output(solution):
    client = MockLLMClient(
        responses=["OUTLINE", "DRAFT", "REVIEW", "FINAL"],
    )
    app = solution.make_draft_graph(client)
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
    assert final["outline"] == "OUTLINE"
    assert final["draft"] == "DRAFT"
    assert final["review"] == "REVIEW"
    assert final["final"] == "FINAL"
    assert final["status"] == "finalized"
    # Exactly one LLM call per node, in order.
    assert len(client.calls) == 4


# --- Lab C: routes correctly for both request types -----------------------


def test_lab_c_routes_simple_to_short(solution):
    final = solution.run_lab_c("What are the office hours?")
    assert final["route"] == "short"
    assert final["complexity"] == "simple"
    assert "short_explanation" in "".join(final["trace"])


def test_lab_c_routes_complex_to_detailed(solution):
    final = solution.run_lab_c("Analyze our GDPR policy for compliance gaps.")
    assert final["route"] == "detailed"
    assert final["complexity"] == "complex"
    assert "detailed_policy_analysis" in "".join(final["trace"])


# --- Lab D: capped when evidence never improves, early when it passes ------


def test_lab_d_stops_at_iteration_cap(solution):
    # Scores stay below the threshold forever -> must stop exactly at the cap.
    final = solution.run_lab_d([0.1, 0.1, 0.1, 0.1, 0.1])
    assert final["iteration"] == solution.MAX_ITERATIONS
    assert final["status"] == "max_iterations_reached"
    # analyze_evidence ran exactly MAX_ITERATIONS times — no infinite loop.
    analyze_count = sum(1 for line in final["trace"] if "analyze_evidence" in line)
    assert analyze_count == solution.MAX_ITERATIONS


def test_lab_d_exits_early_when_evidence_passes(solution):
    final = solution.run_lab_d([0.4, 0.9])
    assert final["iteration"] == 2
    assert final["iteration"] < solution.MAX_ITERATIONS
    assert final["status"] == "sufficient_evidence"


def test_lab_d_passes_on_first_pass(solution):
    final = solution.run_lab_d([0.99])
    assert final["iteration"] == 1
    assert final["status"] == "sufficient_evidence"
