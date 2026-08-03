"""Module 18 tests — the reference solution (always runs).

Guarantees the reference multi-agent lab works end to end offline: the
specialists answer, the supervisor routes, and the comparison shows the
supervisor spending MORE LLM calls than the single agent (the honest cost of
the pattern).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path

MODULE_DIR = Path(__file__).resolve().parents[1]
SOLUTION = MODULE_DIR / "solution" / "multi_agent_lab.py"


@pytest.fixture(scope="module")
def sol():
    return import_from_path("m18_solution_multi_agent_lab", SOLUTION)


def test_solution_runs_offline(monkeypatch, sol):
    monkeypatch.setenv("TECHCORP_OFFLINE", "true")
    assert sol.main() == 0


def test_solution_comparison_supervisor_costs_more(sol):
    """The reference wiring makes the supervisor use strictly more LLM calls than
    the single agent (synthesis is on) — assert and embrace it."""
    store = sol.build_offline_store()
    results = sol.run_comparison(
        sol.QUESTIONS,
        single_agent_fn=sol._single_agent_fn(store),
        supervisor=sol._fresh_supervisor(store),
    )
    single = results["single_agent"]
    multi = results["supervisor"]
    assert multi["llm_calls"] > single["llm_calls"]
    assert results["delta"]["extra_llm_calls"] > 0
    assert multi["total_tokens"] > 0
    # Both systems answered every question (no crashes).
    assert len(single["answers"]) == len(sol.QUESTIONS)
    assert len(multi["answers"]) == len(sol.QUESTIONS)
    assert single["failures"] == 0 and multi["failures"] == 0
