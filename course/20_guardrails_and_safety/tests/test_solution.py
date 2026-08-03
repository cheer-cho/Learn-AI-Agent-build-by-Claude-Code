"""Module 20 tests — the reference solution (always runs, fully offline).

Guarantees the reference safety lab works end to end: the planted injection is
detected and the protected path blocks the leak, output validation catches
missing/invented citations, and the per-session budget warns then refuses — the
module's promise that the planted attacks FAIL against the defenses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path

MODULE_DIR = Path(__file__).resolve().parents[1]
SOLUTION = MODULE_DIR / "solution" / "safety_lab.py"


@pytest.fixture(scope="module")
def sol():
    return import_from_path("m20_solution_safety_lab", SOLUTION)


def test_solution_runs_offline(monkeypatch, sol):
    monkeypatch.setenv("TECHCORP_OFFLINE", "true")
    assert sol.main() == 0


def test_lab_a_before_after_injection(sol):
    """The core demo: same hijacked model output, blocked only when defended."""
    result = sol.lab_a_injection()
    # The planted document is detected as carrying an injection payload.
    assert result["detected"] >= 1
    # Both paths produce identical adversarial model output...
    assert result["identical_model_output"] is True
    # ...but only the protected path (validation) blocks it.
    assert result["protected_blocked"] is True


def test_lab_b_output_validation(sol):
    result = sol.lab_b_output_validation()
    assert result["grounded_ok"] is True
    assert result["missing_blocked"] is True
    assert result["invented_blocked"] is True
    assert result["abstention_ok"] is True


def test_lab_c_budget_warns_then_refuses(sol):
    result = sol.lab_c_budget()
    assert result["warned"] is True
    assert result["refused"] is True
