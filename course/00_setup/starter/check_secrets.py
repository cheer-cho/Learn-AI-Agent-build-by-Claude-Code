"""TechCorp secrets audit — YOUR WORK (Module 00).

Your team lead wants one script the whole team can run before every commit.
It must verify that this repository handles secrets safely:

  (a) `.env` exists                          -> implemented for you, as a model
  (b) `.env` is matched by `.gitignore`      -> TODO (check b)
  (c) `git ls-files` does not list `.env`    -> TODO (check c)
  (d) no file under `src/` or `course/`
      contains an API-key-shaped string      -> TODO (check d)

The script prints a report and exits 0 only when ALL checks pass.
House rule: NEVER print a secret's value — only presence/absence and paths.

Run it from the repository root while you work:

    uv run python course/00_setup/starter/check_secrets.py

While checks are unimplemented they report FAIL and the script exits 1 —
an unfinished audit must not pretend the repo is clean.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# course/00_setup/starter/check_secrets.py -> repository root is 3 levels up.
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# An OpenAI-style secret key: "sk-" followed by MORE THAN 12 key characters.
# Use this pattern for check (d).
KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{13,}")

# Only these top-level directories are scanned for leaked keys.
SCAN_DIRS = ("src", "course")

# Directories that never contain hand-written source — skip them in check (d).
SKIP_DIR_NAMES = {"__pycache__", ".venv", ".git", ".pytest_cache", ".ruff_cache"}

CheckResult = tuple[bool, str]


def check_env_exists(root: Path) -> CheckResult:
    """(a) `.env` must exist at the repository root.  (Worked example.)

    Every check has the same shape: take the repo root, return
    (passed, human-readable detail). Copy this shape for (b), (c), (d).
    """
    if (root / ".env").exists():
        return True, ".env exists"
    return False, "no .env file — run: cp .env.example .env"


def check_env_gitignored(root: Path) -> CheckResult:
    """(b) `.env` must be matched by a `.gitignore` rule.

    Hint: run `git check-ignore .env` with `subprocess.run(...)` using
    `cwd=root` and `capture_output=True`. git signals "some ignore rule
    matches" purely via the return code: 0 = ignored, 1 = not ignored.

    Return (True, "...") when ignored, (False, "... how to fix ...") when not.
    """
    # TODO: call `git check-ignore .env` via subprocess.run and inspect
    #       result.returncode (0 means .env is ignored).
    return False, "TODO: check (b) not implemented yet"


def check_env_not_tracked(root: Path) -> CheckResult:
    """(c) `git ls-files` (everything git tracks/pushes) must not list `.env`.

    Hint: run `git ls-files` with subprocess.run(..., cwd=root,
    capture_output=True, text=True), then split `result.stdout` into lines
    and test whether ".env" is one of them. Compare whole lines, not
    substrings — ".env.example" must not count as a match.
    """
    # TODO: call `git ls-files` via subprocess.run and assert ".env" is not
    #       among the lines of result.stdout.
    return False, "TODO: check (c) not implemented yet"


def check_no_leaked_keys(root: Path) -> CheckResult:
    """(d) No file under src/ or course/ may contain a key-shaped string.

    Hint: for each directory name in SCAN_DIRS, walk `(root / name).rglob("*")`.
    For every regular file (skip any path with a SKIP_DIR_NAMES ancestor),
    read its text — `path.read_bytes().decode("utf-8", errors="ignore")`
    survives binary files — and test it with `KEY_PATTERN.search(...)`.

    Collect the RELATIVE PATHS of offending files and report those paths
    only. Never include the matched text itself: the audit's report must not
    become a second copy of the leak.
    """
    # TODO: walk SCAN_DIRS, scan each file with KEY_PATTERN, and return
    #       (False, "... offending paths ...") if anything matches,
    #       otherwise (True, "no key-shaped strings found").
    return False, "TODO: check (d) not implemented yet"


CHECKS: list[tuple[str, object]] = [
    (".env exists", check_env_exists),
    (".env gitignored", check_env_gitignored),
    (".env not tracked", check_env_not_tracked),
    ("no leaked keys", check_no_leaked_keys),
]


def run_audit(root: Path) -> tuple[bool, list[tuple[str, bool, str]]]:
    """Run every check; return (all_passed, [(label, passed, detail), ...])."""
    results: list[tuple[str, bool, str]] = []
    for label, check in CHECKS:
        try:
            passed, detail = check(root)  # type: ignore[operator]
        except Exception as exc:  # a broken check is a failed check, not a crash
            passed, detail = False, f"check crashed: {exc}"
        results.append((label, passed, detail))
    return all(passed for _, passed, _ in results), results


def main(root: Path = PROJECT_ROOT) -> int:
    ok, results = run_audit(root)
    print(f"\nTechCorp secrets audit — {root.name}\n{'=' * 60}")
    for label, passed, detail in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {label}: {detail}")
    print("=" * 60)
    if ok:
        print("Secrets audit passed. Nothing secret can reach git from here.")
        return 0
    print("Secrets audit FAILED — fix the items above before committing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
