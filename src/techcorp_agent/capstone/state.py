"""The shared LangGraph state for the TechCorp Knowledge Agent v1.

Every node reads and returns a *partial* update of this ``AgentState``;
LangGraph merges each partial into the running state. Two design choices carry
their weight here and are reused unchanged by Modules 15-22:

- ``trace`` uses an ``Annotated[list[str], operator.add]`` *reducer* so that
  when two nodes each return ``{"trace": [...]}`` the lists are **appended**,
  not overwritten (the pattern introduced in Module 10). One accumulating trace
  is what dev mode prints and what the tests assert on.
- ``loop_count`` is an ordinary overwrite field the retrieval retry path bumps;
  the graph caps it so a self-retrying node can never loop forever (Module 10,
  Lab D).

Everything else (``route``, ``evidence``, ``answer``, ``sources``,
``tool_result``) is a plain overwrite field: the last node to set it wins, which
is exactly what we want for a single-turn pipeline.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict, total=False):
    """Shared state threaded through the capstone graph.

    ``total=False`` lets nodes return only the keys they changed and lets the
    CLI seed a minimal initial state (``question`` + ``conversation_id``) without
    having to pre-fill every field.
    """

    # -- identity / input ---------------------------------------------------
    conversation_id: str
    question: str

    # -- routing ------------------------------------------------------------
    # One of: "retrieval", "calculator", "orders", "general".
    route: str

    # -- retrieval / grounded answer ---------------------------------------
    # A short human-readable summary of the retrieved chunks (doc ids + scores),
    # kept in state so dev mode and later modules can inspect what was fetched.
    evidence: str
    sources: list[str]

    # -- tool routes (calculator / orders) ---------------------------------
    # The raw backend outcome (MCP result text or local ToolResult output),
    # before the formatter turns it into a user-facing answer.
    tool_result: str

    # -- output -------------------------------------------------------------
    answer: str

    # -- observability / control -------------------------------------------
    trace: Annotated[list[str], operator.add]
    loop_count: int
