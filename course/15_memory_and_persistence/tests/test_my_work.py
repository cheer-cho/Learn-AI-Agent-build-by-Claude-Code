"""Module 15 tests — your starter implementation.

These auto-skip while starter/memory_lab.py still contains TODO markers. Once you
finish the lab they run and become your completion gate:

    uv run pytest course/15_memory_and_persistence -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/memory_lab.py still contains TODO markers — finish the lab first",
)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m15_starter_memory_lab", STARTER_DIR / "memory_lab.py")


def test_checkpointed_conversation_remembers_and_survives_restart(my_work, tmp_path):
    answers = my_work.demo_checkpointed_conversation(tmp_path / "conv.db")
    assert len(answers) == 2
    assert "30 calendar days" in answers[0]
    assert "Legal and HR" in answers[1]


def test_summarization_shrinks_over_budget_history(my_work):
    tokens_before, tokens_after = my_work.demo_summarization_under_budget()
    assert tokens_after < tokens_before


def test_long_term_preferences_apply_in_a_later_session(my_work, tmp_path):
    answer = my_work.demo_long_term_preferences(tmp_path / "users.db", tmp_path / "session.db")
    assert isinstance(answer, str) and answer


def test_main_runs_offline_end_to_end(my_work):
    assert my_work.main() == 0
