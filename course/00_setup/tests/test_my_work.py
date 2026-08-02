"""Module 00 — tests for YOUR starter work.

Skipped while `starter/check_secrets.py` still contains TODO markers.
Once you finish lab.md step 7, these become your completion gate: they run
the same assertions the reference solution must satisfy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete

MODULE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_DIR.parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/check_secrets.py still has TODO markers — see lab.md step 7",
)

# Assembled so this test file never contains a literal key-shaped string.
FAKE_KEY = "sk-" + "B" * 20


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m00_starter_check", STARTER_DIR / "check_secrets.py")


def test_env_exists_check_passes(my_work):
    passed, detail = my_work.check_env_exists(PROJECT_ROOT)
    assert passed, detail


def test_env_gitignored_check_passes(my_work):
    passed, detail = my_work.check_env_gitignored(PROJECT_ROOT)
    assert passed, detail


def test_env_not_tracked_check_passes(my_work):
    passed, detail = my_work.check_env_not_tracked(PROJECT_ROOT)
    assert passed, detail


def test_no_leaked_keys_check_passes(my_work):
    passed, detail = my_work.check_no_leaked_keys(PROJECT_ROOT)
    assert passed, detail


def test_main_exits_zero_and_reports_every_check(my_work, capsys):
    assert my_work.main(PROJECT_ROOT) == 0
    out = capsys.readouterr().out
    assert out.count("[PASS]") == 4
    assert "[FAIL]" not in out


def test_detects_planted_key_without_printing_it(my_work, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "oops.py").write_text(f'API_KEY = "{FAKE_KEY}"\n', encoding="utf-8")
    passed, detail = my_work.check_no_leaked_keys(tmp_path)
    assert not passed
    assert "oops.py" in detail
    # House rule: report presence/absence only, never the secret value.
    assert FAKE_KEY not in detail


def test_main_exits_nonzero_when_a_check_fails(my_work, tmp_path, capsys):
    assert my_work.main(tmp_path) == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out
