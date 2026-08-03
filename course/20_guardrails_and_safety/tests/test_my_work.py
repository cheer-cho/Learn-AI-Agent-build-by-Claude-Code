"""Module 20 tests — your starter implementation.

These auto-skip while starter/safety_lab.py still contains TODO markers.
Once you finish the lab, they run and become your completion gate:

    uv run pytest course/20_guardrails_and_safety -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/safety_lab.py still contains TODO markers — finish the lab first",
)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m20_starter_safety_lab", STARTER_DIR / "safety_lab.py")


def test_main_runs_offline(my_work, monkeypatch):
    monkeypatch.setenv("TECHCORP_OFFLINE", "true")
    assert my_work.main() == 0


def test_lab_a_detects_and_blocks(my_work):
    result = my_work.lab_a_injection()
    assert result["detected"] >= 1  # Lab A.1: detect_injection wired
    assert result["identical_model_output"] is True
    assert result["protected_blocked"] is True  # Lab A.2 + A.3: sanitize + validate


def test_lab_b_output_validation(my_work):
    result = my_work.lab_b_output_validation()
    assert result["missing_blocked"] is True  # Lab B.1
    assert result["invented_blocked"] is True  # Lab B.2


def test_lab_c_budget_warns_then_refuses(my_work):
    result = my_work.lab_c_budget()
    assert result["warned"] is True  # Lab C.1 + C.2
    assert result["refused"] is True
