"""Module 15 tests — reference solution. Always runs, fully offline.

Proves the reference ``solution/memory_lab.py`` works end to end: the checkpointed
conversation remembers and survives a restart, summarization shrinks an
over-budget history, and long-term preferences reach a later session's prompt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path

MODULE_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def solution():
    return import_from_path("m15_solution_memory_lab", MODULE_DIR / "solution" / "memory_lab.py")


def test_checkpointed_conversation_remembers_and_survives_restart(solution, tmp_path, capsys):
    answers = solution.demo_checkpointed_conversation(tmp_path / "conv.db")
    assert len(answers) == 2
    assert "30 calendar days" in answers[0]
    assert "Legal and HR" in answers[1]
    out = capsys.readouterr().out
    assert "contained turn 1's question: True" in out
    assert "persisted messages in thread: 4" in out


def test_summarization_shrinks_over_budget_history(solution, capsys):
    tokens_before, tokens_after = solution.demo_summarization_under_budget()
    assert tokens_after < tokens_before, "summarization must reduce the token count"
    out = capsys.readouterr().out
    assert "BEFORE" in out and "AFTER" in out
    assert "was_summarized=True" in out
    # The recent turns must survive verbatim in the AFTER view.
    assert "60 days advance notice" in out


def test_long_term_preferences_apply_in_a_later_session(solution, tmp_path, capsys):
    answer = solution.demo_long_term_preferences(tmp_path / "users.db", tmp_path / "session.db")
    assert isinstance(answer, str) and answer
    out = capsys.readouterr().out
    assert "recalled preferences" in out
    assert "carried department: True" in out
    assert "carried length preference: True" in out


def test_main_runs_offline_end_to_end(solution):
    assert solution.main() == 0
