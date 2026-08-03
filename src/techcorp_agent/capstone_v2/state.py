"""The shared LangGraph state for the TechCorp Knowledge Agent **v2**.

v2 is the production rollout: it extends the v1 ``AgentState`` (Module 14) and
the memory ``MemoryAgentState`` (Module 15) with the fields the Level-4 upgrades
need, and reimplements none of them. Two reducer choices carry their weight and
match the earlier modules exactly so the reused nodes feel identical:

- ``messages`` uses an appending reducer (Module 15) so every turn *adds* to the
  running conversation instead of overwriting it — this is what makes a follow-up
  ("how long is that?") resolve against an earlier turn once the graph is
  checkpointed.
- ``trace`` uses ``Annotated[list[str], operator.add]`` (Module 10) so that when
  several nodes each return ``{"trace": [...]}`` the lists are **appended**. One
  accumulating trace is what ``--dev`` prints, what the report reads, and what the
  tests assert on.

Everything else is a plain overwrite field: the last node to set it wins, which
is exactly right for a single-turn pipeline threaded across turns by the
checkpointer.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from techcorp_agent.schemas import ChatMessage


def _messages_reducer(
    existing: list[ChatMessage] | None, update: list[ChatMessage]
) -> list[ChatMessage]:
    """Append new messages to the running history (the Module 15 reducer).

    We keep the history as ``ChatMessage`` objects — the exact type every capstone
    component already speaks — rather than converting to LangChain message
    classes. The checkpointer serializes whatever the reducer produces, so
    persistence works the same either way.
    """
    return list(existing or []) + list(update)


class V2State(TypedDict, total=False):
    """Shared state threaded through the v2 graph.

    ``total=False`` lets nodes return only the keys they changed and lets a caller
    seed a minimal initial state (``question`` + ``trace``) without pre-filling
    every field.
    """

    # -- identity / conversation memory (Module 15) ------------------------
    conversation_id: str
    messages: Annotated[list[ChatMessage], _messages_reducer]
    user_id: str
    preferences: dict[str, str]

    # -- input --------------------------------------------------------------
    question: str

    # -- routing (Module 18 supervisor) ------------------------------------
    # ``route`` is the coarse capability route ("policy" / "support" / "orders" /
    # "general" / "ticket"); ``specialist`` is the specialist the supervisor
    # picked (policy / support / orders) when a knowledge route ran.
    route: str
    specialist: str

    # -- retrieval / grounded answer (Modules 08, 17) ----------------------
    evidence: str
    sources: list[str]

    # -- tool routes (calculator / orders MCP; Modules 13-14) --------------
    tool_result: str

    # -- human-in-the-loop approval (Module 16) ----------------------------
    # Set when the ticket node pauses; the CLI/API surfaces it and resumes.
    pending_approval: dict[str, Any]

    # -- output -------------------------------------------------------------
    answer: str

    # -- safety / budget (Module 20) ---------------------------------------
    # A boundary decision the graph records so dev mode and tests can see it.
    blocked: bool
    budget_info: dict[str, Any]

    # -- observability / control (Modules 10, 19) --------------------------
    trace: Annotated[list[str], operator.add]
    loop_count: int
