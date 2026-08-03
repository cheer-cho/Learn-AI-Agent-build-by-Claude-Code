"""Human-in-the-loop approval gate for a *write* action: create a support ticket.

Every route the capstone agent has so far is **read-only** — retrieval, a
calculator, an order lookup, a chat reply. Module 11's rule was explicit: treat
tools as read-only unless a lab teaches approval. This is that lab. Creating a
support ticket is a *write*: it makes something exist in the outside world that a
customer and a support team will act on. A wrong or hallucinated ticket is not a
bad sentence you can ignore — it is a real artifact. So the ticket action must
not fire on the model's say-so alone; a human approves it first.

The mechanism is a LangGraph **interrupt**. The ticket node calls
``interrupt(payload)`` describing *exactly* what it is about to do; the graph
pauses and its state is saved by a **checkpointer** (Module 15 — persistence is
what makes "pause now, decide later, even after a restart" possible). A human
then resumes with ``Command(resume=decision)``:

- approve -> the node creates the (mock) ticket and returns its id;
- reject  -> the node creates nothing and returns a clear, user-facing message.

Design choices kept deliberately explicit (they are the teaching point):

- **What deserves approval:** write actions, escalations, and spending. Reads do
  not. ``create_ticket`` is the write; the rest of the graph stays un-gated.
- **The payload shows the exact effect** ("a support ticket will be created
  with this summary / order id"), because an approval you cannot understand is
  not consent.
- **The mock action writes nothing external.** ``create_ticket`` returns a
  fictional ``TCK-XXXX`` id computed from its inputs — deterministic, offline,
  and safe to run in tests a thousand times.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from techcorp_agent.llm.base import LLMClient
from techcorp_agent.schemas import ChatMessage
from techcorp_agent.streaming.events import INTERRUPT_KEY

# The one action in this graph that deserves a human gate.
ACTION_CREATE_TICKET = "create_ticket"


# -- the mock write action ---------------------------------------------------


def create_ticket(summary: str, order_id: str | None = None) -> str:
    """Create a support ticket (MOCK) and return its id.

    Writes nothing external: the id is a deterministic ``TCK-XXXX`` derived from
    the inputs, so the same request always yields the same id and tests never
    depend on randomness or a network. In production this is where the real
    ticketing-system call would live — which is exactly why it sits behind the
    approval gate.

    Args:
        summary: the human-readable problem description the ticket will carry.
        order_id: the related order, if any (e.g. ``"TC-2048"``).

    Returns:
        A fictional ticket id like ``"TCK-4F2A"``.
    """
    seed = f"{summary}|{order_id or ''}".encode()
    digest = hashlib.sha256(seed).hexdigest()[:4].upper()
    return f"TCK-{digest}"


# -- graph state -------------------------------------------------------------


class ApprovalState(TypedDict, total=False):
    """State for the approval graph.

    Kept separate from the capstone ``AgentState`` on purpose: this is a small,
    focused HITL graph, not the full agent. ``question`` is the user's request;
    ``summary`` / ``order_id`` describe the ticket to be created; ``ticket_id``
    and ``result`` are the outcome (one or the other, never a partial write).
    """

    question: str
    summary: str
    order_id: str | None
    ticket_id: str
    result: str


# -- result / pending types --------------------------------------------------


@dataclass
class PendingApproval:
    """Returned when the graph has paused and is waiting for a human decision.

    Attributes:
        payload: exactly what the ticket node is about to do — show this to the
            human verbatim before they approve.
        thread_id: the checkpointer thread to resume; pass it to
            :func:`resume_with_decision`. It survives a process restart, which is
            what makes "approve it tomorrow" work.
    """

    payload: dict[str, Any]
    thread_id: str


@dataclass
class TicketResult:
    """Returned once the graph has finished (approved or rejected).

    Attributes:
        approved: whether the human approved the action.
        message: the user-facing outcome text.
        ticket_id: the created ticket id when approved, else ``None``.
    """

    approved: bool
    message: str
    ticket_id: str | None = None


# -- graph construction ------------------------------------------------------


def build_approval_graph(llm: LLMClient, checkpointer: Any):
    """Build the approval-gated ticket graph.

    Flow::

        START -> prepare -> ticket(interrupt!) -> END

    ``prepare`` uses the LLM to distill the user's request into a one-line ticket
    summary (offline the mock returns a scripted line) and pulls out an order id
    if present. ``ticket`` calls ``interrupt(...)`` with a payload describing the
    exact write, pausing the graph; on resume it either creates the ticket or
    cancels.

    Args:
        llm: the application LLM client (mock offline, real with a key).
        checkpointer: a LangGraph checkpointer — **required**. Interrupt/resume
            only works because the paused state is saved somewhere; pass a
            ``MemorySaver`` for in-process tests or a ``SqliteSaver`` for a gate
            that survives a restart (Module 15). ``None`` is rejected loudly so
            the failure is a clear message, not a confusing runtime error.

    Returns:
        A compiled, interruptible LangGraph.
    """
    if checkpointer is None:
        raise ValueError(
            "build_approval_graph requires a checkpointer: interrupt/resume "
            "needs the paused state persisted. Pass MemorySaver() (in-process) "
            "or SqliteSaver(conn) (survives a restart)."
        )

    def prepare_node(state: ApprovalState) -> dict:
        """Turn the raw request into a concrete, reviewable ticket spec."""
        question = state["question"]
        order_id = _extract_order_id(question)
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are TechCorp support triage. Summarize the customer's "
                    "issue in one short sentence suitable for a ticket title. "
                    "Do not add greetings or resolutions."
                ),
            ),
            ChatMessage(role="user", content=question),
        ]
        try:
            summary = llm.complete(messages, temperature=0.0).content.strip()
        except Exception as exc:  # noqa: BLE001 - an LLM failure is data, not a crash
            summary = f"Support request (summary unavailable: {exc})"
        return {"summary": summary or question, "order_id": order_id}

    def ticket_node(state: ApprovalState) -> dict:
        """Gate the write behind a human decision, then act on it.

        ``interrupt(payload)`` pauses the graph *before* anything is created and
        hands ``payload`` to the human. Execution stops here; nothing below the
        ``interrupt`` line runs until someone resumes with ``Command(resume=...)``.
        On resume, ``interrupt`` returns that resume value.
        """
        summary = state.get("summary", state["question"])
        order_id = state.get("order_id")
        payload = {
            "action": ACTION_CREATE_TICKET,
            "description": "A support ticket will be created with the details below.",
            "summary": summary,
            "order_id": order_id,
        }
        decision = interrupt(payload)  # <-- graph pauses here until resumed
        approved = _decision_is_approval(decision)
        if not approved:
            return {
                "result": (
                    "No ticket was created — you rejected the request. "
                    "Nothing was sent to the support system."
                ),
            }
        ticket_id = create_ticket(summary, order_id)
        order_note = f" for order {order_id}" if order_id else ""
        return {
            "ticket_id": ticket_id,
            "result": f"Created support ticket {ticket_id}{order_note}: {summary}",
        }

    graph = StateGraph(ApprovalState)
    graph.add_node("prepare", prepare_node)
    graph.add_node("ticket", ticket_node)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "ticket")
    graph.add_edge("ticket", END)
    return graph.compile(checkpointer=checkpointer)


# -- driver helpers ----------------------------------------------------------


def start_ticket_request(
    graph: Any, question: str, thread_id: str
) -> TicketResult | PendingApproval:
    """Start a ticket request; pause at the approval gate.

    Runs the graph up to the ``interrupt`` in the ticket node. Because the ticket
    node *always* interrupts before creating anything, a fresh request normally
    returns a :class:`PendingApproval` — the mock ``create_ticket`` has NOT been
    called yet. (If a future edit removed the gate this would return a finished
    :class:`TicketResult` instead, which is why the return type is a union.)

    Args:
        graph: a compiled approval graph from :func:`build_approval_graph`.
        question: the user's request, e.g. "create a support ticket for my
            damaged AeroBook order TC-2048".
        thread_id: the conversation/thread id to run under; the same id is used
            to resume, and it is what persists across a restart.

    Returns:
        :class:`PendingApproval` if the graph paused for approval, else a
        :class:`TicketResult` if it somehow finished without interrupting.
    """
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"question": question}, config)
    pending = _pending_from_result(result, thread_id)
    if pending is not None:
        return pending
    return _finished_result(result)


def resume_with_decision(graph: Any, thread_id: str, approved: bool) -> TicketResult:
    """Resume a paused ticket request with the human's decision.

    Reuses the SAME ``thread_id``, so the graph picks up exactly where it paused
    (the checkpointer restored ``summary`` and ``order_id``) — including in a
    brand-new process, as long as the checkpointer is durable (Sqlite).

    Args:
        graph: the compiled approval graph (rebuilt against the same
            checkpointer if this is a new process).
        thread_id: the thread returned in the :class:`PendingApproval`.
        approved: ``True`` to create the ticket, ``False`` to cancel gracefully.

    Returns:
        A :class:`TicketResult`: on approve, ``ticket_id`` is set; on reject,
        ``ticket_id`` is ``None`` and ``message`` explains nothing was created.
    """
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(Command(resume="approve" if approved else "reject"), config)
    return _finished_result(result)


# -- internals ---------------------------------------------------------------


def _pending_from_result(result: Any, thread_id: str) -> PendingApproval | None:
    """Build a :class:`PendingApproval` if ``result`` carries an interrupt."""
    if not isinstance(result, dict) or INTERRUPT_KEY not in result:
        return None
    interrupts = result[INTERRUPT_KEY]
    first = interrupts[0] if isinstance(interrupts, (tuple, list)) else interrupts
    payload = getattr(first, "value", first)
    return PendingApproval(payload=payload, thread_id=thread_id)


def _finished_result(result: Any) -> TicketResult:
    """Normalize a finished graph state into a :class:`TicketResult`."""
    ticket_id = result.get("ticket_id") if isinstance(result, dict) else None
    message = result.get("result", "") if isinstance(result, dict) else ""
    return TicketResult(
        approved=ticket_id is not None,
        message=message or ("Ticket created." if ticket_id else "Request cancelled."),
        ticket_id=ticket_id,
    )


def _decision_is_approval(decision: Any) -> bool:
    """Interpret a resume value as approve/reject, permissively.

    Accepts booleans and common strings so callers can resume with
    ``Command(resume=True)`` or ``Command(resume="approve")`` interchangeably.
    """
    if isinstance(decision, bool):
        return decision
    if isinstance(decision, str):
        return decision.strip().lower() in {"approve", "approved", "yes", "y", "true"}
    return bool(decision)


def _extract_order_id(text: str) -> str | None:
    """Pull a TechCorp order id (``TC-1234``) out of free text, if present."""
    import re

    match = re.search(r"\bTC-\d{3,}\b", text, re.IGNORECASE)
    return match.group(0).upper() if match else None
