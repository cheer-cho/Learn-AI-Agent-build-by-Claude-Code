"""Event streaming: turn a running graph into a live, human-readable feed.

Token streaming (``token_stream.py``) answers "what is the model *saying*?".
Event streaming answers a different question — "what is the agent *doing*?" —
and it has a different consumer. Tokens are for the human reading the answer;
events are for a human (or, in Module 21, a UI / monitor) watching the graph
work: which node ran, what state keys it changed, which route it picked.

LangGraph exposes this through ``graph.stream(state, config, stream_mode=...)``.
The mode this module uses is ``"updates"``: it yields one dict per super-step,
mapping the node name to the *partial* state update that node returned — in
execution order. (The other modes, probed in ``concepts.md``: ``"values"``
yields the whole accumulated state after each step; ``"messages"`` yields LLM
tokens for graphs that stream from chat models.)

:func:`stream_agent_events` normalizes those raw update dicts into small,
serializable :class:`AgentEvent` records that read well in a CLI *and* map
cleanly onto Server-Sent Events later (Module 21 reuses this — it does not
reinvent it). A special ``__interrupt__`` update (Module 16's approval gate)
becomes an ``interrupt`` event carrying the payload the human must decide on.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

# The key LangGraph uses in an ``updates``/``values`` stream to signal that a
# node called ``interrupt()`` and the graph has paused.
INTERRUPT_KEY = "__interrupt__"

# State keys we surface as the "route selected" event when a node sets them.
_ROUTE_KEYS = ("route",)


@dataclass
class AgentEvent:
    """One normalized, human-readable thing that happened while the graph ran.

    Attributes:
        type: ``"node"`` (a node produced an update), ``"route"`` (a routing
            decision was made), or ``"interrupt"`` (the graph paused for a human).
        node: the node that produced the update (``""`` for framework events).
        summary: a one-line, human-facing description suitable for a CLI.
        updated_keys: the state keys this node changed (empty for interrupts).
        payload: for ``interrupt`` events, the interrupt value (what the human
            must approve); otherwise ``None``.
    """

    type: str
    node: str
    summary: str
    updated_keys: list[str] = field(default_factory=list)
    payload: Any = None

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.summary


def _interrupt_payload(update: Any) -> Any:
    """Extract the human-facing payload from an ``__interrupt__`` update.

    The value LangGraph puts under ``__interrupt__`` is a tuple/list of
    ``Interrupt`` objects (each with a ``.value``). We surface the first one's
    value — the payload the ticket node passed to ``interrupt(...)``.
    """
    if isinstance(update, (tuple, list)) and update:
        first = update[0]
        return getattr(first, "value", first)
    return getattr(update, "value", update)


def _events_for_node(node: str, update: Any) -> Iterator[AgentEvent]:
    """Yield the normalized event(s) for one node's raw update dict."""
    if node == INTERRUPT_KEY:
        payload = _interrupt_payload(update)
        action = payload.get("action") if isinstance(payload, dict) else None
        summary = f"paused for human approval: {action}" if action else "paused for human approval"
        yield AgentEvent(type="interrupt", node="", summary=summary, payload=payload)
        return

    keys = sorted(update.keys()) if isinstance(update, dict) else []
    yield AgentEvent(
        type="node",
        node=node,
        summary=f"node '{node}' updated {keys}" if keys else f"node '{node}' ran",
        updated_keys=keys,
    )

    # A routing decision is worth calling out on its own line: it explains why
    # the *next* node will be what it is.
    if isinstance(update, dict):
        for route_key in _ROUTE_KEYS:
            if route_key in update:
                yield AgentEvent(
                    type="route",
                    node=node,
                    summary=f"route selected: {update[route_key]}",
                    updated_keys=[route_key],
                )


def stream_agent_events(
    graph: Any,
    state: Any,
    config: dict | None = None,
    *,
    stream_mode: str = "updates",
) -> Iterator[AgentEvent]:
    """Run ``graph`` and yield normalized :class:`AgentEvent` records live.

    Wraps ``graph.stream(state, config, stream_mode="updates")`` — one raw update
    dict per node, in execution order — and translates each into human-readable
    events. The router's update comes before the formatter's, so a caller
    printing these sees the nodes "light up" in the order they ran.

    Args:
        graph: a compiled LangGraph (e.g. the capstone ``build_graph`` output).
        state: the initial state to run, or a ``Command`` to resume with.
        config: the run config (e.g. ``{"configurable": {"thread_id": ...}}``);
            required for checkpointed/interruptible graphs, optional otherwise.
        stream_mode: passed through to ``graph.stream``; ``"updates"`` (default)
            is the one this normalizer understands.

    Yields:
        :class:`AgentEvent` records, in execution order. If a node interrupts,
        an ``interrupt`` event carrying the approval payload is the last one.
    """
    for step in graph.stream(state, config, stream_mode=stream_mode):
        if not isinstance(step, dict):
            # Defensive: other stream modes yield non-dict steps we don't map.
            continue
        for node, update in step.items():
            yield from _events_for_node(node, update)
