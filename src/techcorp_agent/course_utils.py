"""Helpers for course-module tests.

Convention used by every module:

- `tests/test_solution.py` imports from `solution/` and always runs — it
  guarantees the reference implementation works (course integrity).
- `tests/test_my_work.py` imports from `starter/` and auto-skips while the
  learner's starter still contains TODO markers — it becomes the learner's
  completion gate once they start working.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

TODO_MARKER = "TODO"


def starter_incomplete(starter_dir: Path) -> bool:
    """True while any Python file in the starter directory still has a TODO marker."""
    return any(TODO_MARKER in path.read_text(encoding="utf-8") for path in starter_dir.glob("*.py"))


def import_from_path(module_name: str, file_path: Path) -> ModuleType:
    """Import a single Python file under a unique module name.

    Starter and solution directories are not packages; this loads a specific
    file (e.g. `solution/explorer.py`) so tests can call its functions.
    Use a unique module_name per module+variant (e.g. 'm01_solution_explorer')
    to avoid clashes in sys.modules.
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
