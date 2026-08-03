"""Module 00 — tests for the reference solution (always run, offline).

These guarantee the reference secrets audit works against the real repo,
plus directly verify the repo-level invariants the audit relies on:
`.gitignore` covers `.env` and git does not track `.env`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path

MODULE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_DIR.parents[1]

solution = import_from_path("m00_solution_check", MODULE_DIR / "solution" / "check_secrets.py")


@pytest.fixture
def env_file_present():
    """Guarantee a repo-root .env exists for audit tests that require it.

    A fresh checkout (CI, a clone before `make setup`) has no .env because it is
    gitignored. Create one from .env.example if absent, and remove it afterward
    only if this fixture created it — never clobber a learner's real .env."""
    env_path = PROJECT_ROOT / ".env"
    created = False
    if not env_path.exists():
        env_path.write_text(
            (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8"
        )
        created = True
    try:
        yield env_path
    finally:
        if created:
            env_path.unlink(missing_ok=True)


# A key-shaped string for negative tests, assembled so that this test file
# itself never contains a literal match for the audit's pattern.
FAKE_KEY = "sk-" + "A" * 20


def test_env_exists_check_passes(env_file_present):
    passed, detail = solution.check_env_exists(PROJECT_ROOT)
    assert passed, detail


def test_env_gitignored_check_passes():
    passed, detail = solution.check_env_gitignored(PROJECT_ROOT)
    assert passed, detail


def test_env_not_tracked_check_passes():
    passed, detail = solution.check_env_not_tracked(PROJECT_ROOT)
    assert passed, detail


def test_no_leaked_keys_check_passes():
    passed, detail = solution.check_no_leaked_keys(PROJECT_ROOT)
    assert passed, detail


def test_main_exits_zero_and_reports_every_check(env_file_present, capsys):
    assert solution.main(PROJECT_ROOT) == 0
    out = capsys.readouterr().out
    assert out.count("[PASS]") == 4
    assert "[FAIL]" not in out
    assert "Secrets audit passed" in out


def test_detects_planted_key_without_printing_it(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "oops.py").write_text(f'API_KEY = "{FAKE_KEY}"\n', encoding="utf-8")
    passed, detail = solution.check_no_leaked_keys(tmp_path)
    assert not passed
    assert "oops.py" in detail
    # Presence/absence only — the report must never contain the secret value.
    assert FAKE_KEY not in detail


def test_main_exits_nonzero_when_a_check_fails(tmp_path, capsys):
    # tmp_path has no .env and is not a git repo: several checks must fail.
    assert solution.main(tmp_path) == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "Secrets audit FAILED" in out


def test_gitignore_covers_env():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore.splitlines()
    result = subprocess.run(
        ["git", "check-ignore", ".env"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, ".env is not matched by any .gitignore rule"


def test_git_ls_files_excludes_env():
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert ".env" not in result.stdout.splitlines()
