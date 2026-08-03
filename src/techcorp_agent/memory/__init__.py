"""Module 15 — memory and persistence for the TechCorp Knowledge Agent.

This package turns the stateless v1 capstone into an agent that remembers a
conversation across turns and restarts, keeps that history under a token budget,
and carries durable per-user facts into future sessions — all without editing a
single capstone file (it *composes* the capstone's pipeline, router, and tools).

- :mod:`techcorp_agent.memory.checkpointing` — the SQLite-checkpointed graph
  (:func:`build_memory_graph`) and the :func:`ask` conversation helper.
- :mod:`techcorp_agent.memory.summarization` — token-budget management: estimate
  history size, summarize older turns, and apply a budget.
- :mod:`techcorp_agent.memory.long_term` — the :class:`UserMemoryStore` of durable
  user facts and :func:`inject_preferences` to apply them to a prompt.
"""

from __future__ import annotations

from techcorp_agent.memory.checkpointing import (
    MemoryAgentState,
    ask,
    build_memory_graph,
)
from techcorp_agent.memory.long_term import UserMemoryStore, inject_preferences
from techcorp_agent.memory.summarization import (
    apply_budget,
    estimate_history_tokens,
    summarize_history,
)

__all__ = [
    "MemoryAgentState",
    "UserMemoryStore",
    "apply_budget",
    "ask",
    "build_memory_graph",
    "estimate_history_tokens",
    "inject_preferences",
    "summarize_history",
]
