"""Module 16 starter — Streaming and Human-in-the-Loop.

Fill in the TODOs, then run:

    uv run python course/16_streaming_and_hitl/starter/streaming_lab.py

The four labs each become a small function the tests call:

- Lab A  stream_answer_to_cli   — token streaming
- Lab B  stream_workflow_events — event streaming
- Lab C  run_approval_gate      — interrupt + approve/reject
- Lab D  resume_after_restart   — resume the same thread_id on a fresh graph

Read src/techcorp_agent/streaming/ (token_stream.py, events.py, approval.py) —
you are *using* that package here, not rebuilding it. Everything runs offline.
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
    """Stream a reply chunk by chunk, printing as it arrives; return the full text."""
    chunks: list[str] = []
    # TODO: iterate over client.stream_complete(messages). For each chunk:
    #   - append it to `chunks`
    #   - if echo: print(chunk, end="", flush=True)   # note end="" and flush=True
    # After the loop, if echo, print() a final newline.
    # Return the reassembled full text using collect(chunks).
    raise NotImplementedError("Lab A: stream the chunks, then return collect(chunks)")


# -- Lab B — event streaming -------------------------------------------------


def stream_workflow_events(graph, state, *, echo: bool = True) -> list[AgentEvent]:
    """Run the capstone graph and stream its workflow events; return them all."""
    events: list[AgentEvent] = []
    # TODO: iterate over stream_agent_events(graph, state). For each event:
    #   - append it to `events`
    #   - if echo: print a readable line, e.g. f"  · {event.summary}"
    # Return the full list of events.
    raise NotImplementedError("Lab B: collect and print the AgentEvents in order")


# -- Lab C — approval gate ---------------------------------------------------


def run_approval_gate(question: str, *, approve: bool, echo: bool = True) -> TicketResult:
    """Drive the full approval gate for one decision (approve or reject)."""
    llm = MockLLMClient(responses=["Damaged AeroBook on delivery"])
    graph = build_approval_graph(llm, MemorySaver())
    thread_id = "lab-c-approve" if approve else "lab-c-reject"

    # TODO (1): start the request and pause at the gate.
    #   pending = start_ticket_request(graph, question, thread_id)
    #   It should return a PendingApproval — NO ticket has been created yet.
    pending = None  # replace me

    if not isinstance(pending, PendingApproval):
        return pending  # type: ignore[return-value]

    if echo:
        p = pending.payload
        print("  ⏸ APPROVAL REQUIRED — the agent wants to perform a write:")
        print(f"      action:   {p['action']}")
        print(f"      summary:  {p['summary']}")
        print(f"      order id: {p['order_id']}")
        print(f"      decision: {'APPROVE' if approve else 'REJECT'}")

    # TODO (2): resume with the human's decision and return the TicketResult.
    #   result = resume_with_decision(graph, pending.thread_id, approved=approve)
    raise NotImplementedError("Lab C: start, show the payload, then resume with the decision")


# -- Lab D — resume after restart --------------------------------------------


def resume_after_restart(question: str, *, echo: bool = True) -> TicketResult:
    """Prove a pending approval survives a process restart via Sqlite."""
    db_path = Path(tempfile.mkdtemp()) / "approvals.sqlite"
    thread_id = "lab-d-durable"

    # --- "Process 1": start and pause, then close the connection (as on exit) ---
    conn1 = sqlite3.connect(db_path, check_same_thread=False)
    graph1 = build_approval_graph(
        MockLLMClient(responses=["Damaged AeroBook on delivery"]), SqliteSaver(conn1)
    )
    # TODO (1): start_ticket_request against graph1 with `thread_id`, then close conn1.
    conn1.close()

    # --- "Process 2": a NEW graph over the SAME file resumes the SAME thread ---
    conn2 = sqlite3.connect(db_path, check_same_thread=False)
    graph2 = build_approval_graph(
        MockLLMClient(responses=["(unused on resume)"]), SqliteSaver(conn2)
    )
    # TODO (2): resume_with_decision(graph2, thread_id, approved=True), close conn2,
    #           and return the TicketResult. It must have a real TCK- ticket id.
    raise NotImplementedError("Lab D: resume the same thread_id on a fresh Sqlite-backed graph")


# -- driver ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    print("LAB A — Token streaming")
    messages = [
        ChatMessage(role="system", content="You are TechCorp's internal assistant."),
        ChatMessage(role="user", content=DRESS_CODE_QUESTION),
    ]
    client = MockStreamingLLM(
        responses=["Yes — jeans are acceptable under business-casual at headquarters."]
    )
    print(f"  Q: {DRESS_CODE_QUESTION}\n  A: ", end="")
    stream_answer_to_cli(client, messages)

    print("\nLAB B — Workflow event streaming")
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
    stream_workflow_events(graph, state)

    print("\nLAB C — Approval gate")
    run_approval_gate(TICKET_QUESTION, approve=True)
    run_approval_gate(TICKET_QUESTION, approve=False)

    print("\nLAB D — Resume after restart")
    resume_after_restart(TICKET_QUESTION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
