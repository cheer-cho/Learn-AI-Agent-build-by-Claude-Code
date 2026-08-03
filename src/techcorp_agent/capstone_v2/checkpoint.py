"""Checkpointer construction for the v2 graph — memory + resumable approval.

Two facts drive this tiny module:

- The v2 graph *always* needs a checkpointer, because the Module 16 approval
  interrupt only works if the paused state is persisted somewhere.
- When a ``db_path`` is given, that checkpointer should be a **durable**
  ``SqliteSaver`` so multi-turn conversations and pending approvals survive a
  process restart (Module 15). When it is not, an in-memory saver is enough for a
  single-process run or a test.

We reuse Module 15's exact SQLite setup (a caller-owned connection with
``check_same_thread=False`` and a serializer that allows our ``ChatMessage`` in
the persisted checkpoint) rather than re-deriving it, so the durability
guarantees match the memory module the API already depends on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def make_checkpointer(db_path: str | Path | None) -> Any:
    """Return a checkpointer for the v2 graph.

    Args:
        db_path: SQLite file path for a durable saver, or ``None`` for an
            in-memory saver (single process; state is lost on exit).

    Returns:
        A LangGraph checkpointer ready to pass to ``graph.compile(checkpointer=)``.
    """
    if db_path is None:
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    # Reuse Module 15's durable SqliteSaver construction verbatim.
    from techcorp_agent.memory.checkpointing import _make_checkpointer

    return _make_checkpointer(db_path)
