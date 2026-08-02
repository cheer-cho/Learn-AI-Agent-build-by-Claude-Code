"""TechCorp secrets audit — reference implementation (Module 00).

Verifies that this repository handles secrets safely:

  (a) `.env` exists (your private config lives in a real file, not in code),
  (b) `.env` is matched by `.gitignore` (git is told to ignore it),
  (c) `git ls-files` does not list `.env` (git actually tracks no such file),
  (d) no file under `src/` or `course/` contains an API-key-shaped string.

Prints a report and exits 0 when all checks pass, 1 otherwise.
Secret VALUES are never printed — only presence/absence and file paths.

Run offline from the repository root:

    uv run python course/00_setup/solution/check_secrets.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# course/00_setup/solution/check_secrets.py -> repository root is 3 levels up.
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# An OpenAI-style secret key: "sk-" followed by MORE THAN 12 key characters.
# (Short doc snippets like "sk-XXXX" intentionally stay below the threshold.)
KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{13,}")

# Only these top-level directories are scanned for leaked keys.
SCAN_DIRS = ("src", "course")

# Directories that never contain hand-written source.
SKIP_DIR_NAMES = {"__pycache__", ".venv", ".git", ".pytest_cache", ".ruff_cache"}

CheckResult = tuple[bool, str]


def check_env_exists(root: Path) -> CheckResult:
    """(a) `.env` must exist at the repository root."""
    if (root / ".env").exists():
        return True, ".env exists"
    return False, "no .env file — run: cp .env.example .env"


def check_env_gitignored(root: Path) -> CheckResult:
    """(b) `.env` must be matched by a `.gitignore` rule.

    `git check-ignore .env` exits 0 when some ignore rule matches the path,
    and 1 when nothing ignores it.
    """
    result = subprocess.run(
        ["git", "check-ignore", ".env"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, ".env is matched by .gitignore"
    return False, ".env is NOT gitignored — add a `.env` line to .gitignore"


def check_env_not_tracked(root: Path) -> CheckResult:
    """(c) `git ls-files` (everything git tracks) must not contain `.env`."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    tracked = result.stdout.splitlines()
    if ".env" in tracked:
        return False, ".env IS tracked by git — untrack it: git rm --cached .env"
    return True, ".env is not in git's tracked files"


def _iter_scannable_files(root: Path) -> list[Path]:
    """Every file under the SCAN_DIRS trees, skipping cache/venv directories."""
    files: list[Path] = []
    for dir_name in SCAN_DIRS:
        base = root / dir_name
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if SKIP_DIR_NAMES.intersection(part.name for part in path.parents):
                continue
            files.append(path)
    return files


def check_no_leaked_keys(root: Path) -> CheckResult:
    """(d) No file under src/ or course/ may contain a key-shaped string.

    Reports offending FILE PATHS only — never the matched text, because the
    audit's own report must not become a second copy of the leak.
    """
    files = _iter_scannable_files(root)
    offenders: list[str] = []
    for path in files:
        text = path.read_bytes().decode("utf-8", errors="ignore")
        if KEY_PATTERN.search(text):
            offenders.append(str(path.relative_to(root)))
    if offenders:
        listing = ", ".join(offenders)
        return False, f"key-shaped string found in: {listing} — remove it before committing"
    scanned_dirs = " and ".join(f"{name}/" for name in SCAN_DIRS)
    return True, f"no key-shaped strings in {len(files)} files under {scanned_dirs}"


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
