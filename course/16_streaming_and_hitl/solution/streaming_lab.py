"""Module 16 solution — Streaming and Human-in-the-Loop, all four labs, offline.

Run every lab (deterministic, no API key):

    TECHCORP_OFFLINE=true uv run python course/16_streaming_and_hitl/solution/streaming_lab.py

Optional live token streaming (needs OPENAI_API_KEY in .env):

    uv run python course/16_streaming_and_hitl/solution/streaming_lab.py --live

The four labs, each a small function the tests call directly:

- Lab A  stream_answer_to_cli   — token streaming (answer types itself)
- Lab B  stream_workflow_events — event streaming (nodes light up in order)
- Lab C  run_approval_gate      — interrupt, then approve AND reject paths
- Lab D  resume_after_restart   — a fresh graph resumes the same thread_id
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from techcorp_agent.capstone import build_graph, build_offline_store
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage
from techcorp_agent.streaming import (
    AgentEvent,
    MockStreamingLLM,
    PendingApproval,
    TicketResult,
    build_approval_graph,
    collect,
    resume_with_decision,
    start_ticket_request,
    stream_agent_events,
)

TICKET_QUESTION = "Please create a support ticket for my damaged AeroBook order TC-2048."
DRESS_CODE_QUESTION = "Am I allowed to wear jeans under the dress code at headquarters?"


# -- Lab A — token streaming -------------------------------------------------


def stream_answer_to_cli(client, messages: list[ChatMessage], *, echo: bool = True) -> str:
    """Stream a reply chunk by chunk, printing as it arrives; return the full text.

    The point: nothing is buffered until the end. Each chunk is printed the
    instant it is produced, so the answer *types itself*. ``collect`` (here via a
    running list) reassembles the chunks into the exact final string — streaming
    is a delivery choice, not a different answer.
    """
    chunks: list[str] = []
    for chunk in client.stream_complete(messages):
        chunks.append(chunk)
        if echo:
            print(chunk, end="", flush=True)
    if echo:
        print()
    return collect(chunks)


# -- Lab B — event streaming -------------------------------------------------


def stream_workflow_events(graph, state, *, echo: bool = True) -> list[AgentEvent]:
    """Run the capstone graph and stream its workflow events; return them all.

    Each ``AgentEvent`` is a readable line describing what the graph just did:
    which node ran, what state keys it changed, which route it chose. In a CLI
    these are the nodes "lighting up" in execution order.
    """
    events: list[AgentEvent] = []
    for event in stream_agent_events(graph, state):
        events.append(event)
        if echo:
            marker = {"node": "·", "route": "→", "interrupt": "⏸"}.get(event.type, "·")
            print(f"  {marker} {event.summary}")
    return events


# -- Lab C — approval gate ---------------------------------------------------


def run_approval_gate(question: str, *, approve: bool, echo: bool = True) -> TicketResult:
    """Drive the full approval gate for one decision (approve or reject).

    Builds an approval graph with an in-memory checkpointer, starts the request
    (which pauses at the interrupt with NO ticket created yet), shows the human
    exactly what would happen, then resumes with the decision.
    """
    llm = MockLLMClient(responses=["Damaged AeroBook on delivery"])
    graph = build_approval_graph(llm, MemorySaver())
    thread_id = "lab-c-approve" if approve else "lab-c-reject"

    pending = start_ticket_request(graph, question, thread_id)
    if not isinstance(pending, PendingApproval):
        # Should not happen: the gate always pauses first.
        return pending  # type: ignore[return-value]

    if echo:
        p = pending.payload
        print("  ⏸ APPROVAL REQUIRED — the agent wants to perform a write:")
        print(f"      action:   {p['action']}")
        print(f"      summary:  {p['summary']}")
        print(f"      order id: {p['order_id']}")
        print(f"      decision: {'APPROVE' if approve else 'REJECT'}")

    result = resume_with_decision(graph, pending.thread_id, approved=approve)
    if echo:
        print(f"  → {result.message}")
    return result


# -- Lab D — resume after restart --------------------------------------------


def resume_after_restart(question: str, *, echo: bool = True) -> TicketResult:
    """Prove a pending approval survives a process restart via Sqlite.

    "Process 1" starts the request against a temp-file ``SqliteSaver`` and pauses,
    then closes its connection (as an exiting process would). "Process 2" is a
    brand-new graph over the *same file*; it resumes the *same thread_id* and
    finishes the decision. The state was never in this second graph's memory — it
    came back off disk.
    """
    db_path = Path(tempfile.mkdtemp()) / "approvals.sqlite"
    thread_id = "lab-d-durable"

    # --- Process 1: start and pause, then "exit" ---
    conn1 = sqlite3.connect(db_path, check_same_thread=False)
    graph1 = build_approval_graph(
        MockLLMClient(responses=["Damaged AeroBook on delivery"]), SqliteSaver(conn1)
    )
    pending = start_ticket_request(graph1, question, thread_id)
    conn1.close()
    if echo:
        print(f"  ⏸ process 1 paused, state saved to {db_path.name} (thread={thread_id})")
        print("     ...process 1 exits; nothing about this request is in memory now...")

    # --- Process 2: fresh graph, same file, same thread, resume ---
    conn2 = sqlite3.connect(db_path, check_same_thread=False)
    graph2 = build_approval_graph(
        MockLLMClient(responses=["(unused on resume)"]), SqliteSaver(conn2)
    )
    result = resume_with_decision(graph2, thread_id, approved=True)
    conn2.close()
    if echo:
        print(f"  → process 2 recovered the pending approval and finished: {result.message}")
    _ = pending  # (only used to show the pause happened)
    return result


# -- driver ------------------------------------------------------------------


def _token_client(live: bool):
    """MockStreamingLLM offline; the live OpenAI streamer only with a key."""
    if not live:
        return MockStreamingLLM(
            responses=[
                "Yes — jeans are acceptable under TechCorp's business-casual dress "
                "code at headquarters, as long as they are clean and undamaged."
            ]
        )
    from techcorp_agent.config import get_settings
    from techcorp_agent.streaming import OpenAIStreamingClient

    settings = get_settings()
    if settings.offline:
        print("  (no API key configured — falling back to the offline mock)")
        return _token_client(live=False)
    return OpenAIStreamingClient(settings)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    live = "--live" in argv

    print("=" * 70)
    print("LAB A — Token streaming (the answer types itself)")
    print("=" * 70)
    messages = [
        ChatMessage(role="system", content="You are TechCorp's internal assistant."),
        ChatMessage(role="user", content=DRESS_CODE_QUESTION),
    ]
    print(f"  Q: {DRESS_CODE_QUESTION}\n  A: ", end="")
    stream_answer_to_cli(_token_client(live), messages)

    print("\n" + "=" * 70)
    print("LAB B — Workflow event streaming (watch the nodes light up)")
    print("=" * 70)
    store = build_offline_store(persist_dir=Path(tempfile.mkdtemp()))
    llm = MockLLMClient(
        responses=["document_search", "Yes, jeans are fine.\nSOURCES: hr-dress-code"]
    )
    graph = build_graph(llm, store)
    state = {
        "conversation_id": "lab-b",
        "question": DRESS_CODE_QUESTION,
        "trace": [],
        "loop_count": 0,
    }
    print(f"  Q: {DRESS_CODE_QUESTION}")
    stream_workflow_events(graph, state)

    print("\n" + "=" * 70)
    print("LAB C — Approval gate (a write needs a human yes/no)")
    print("=" * 70)
    print(f"  Q: {TICKET_QUESTION}\n")
    print("  --- APPROVE path ---")
    run_approval_gate(TICKET_QUESTION, approve=True)
    print("\n  --- REJECT path ---")
    run_approval_gate(TICKET_QUESTION, approve=False)

    print("\n" + "=" * 70)
    print("LAB D — Resume after restart (the pending approval survives)")
    print("=" * 70)
    resume_after_restart(TICKET_QUESTION)

    print("\nAll labs complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
