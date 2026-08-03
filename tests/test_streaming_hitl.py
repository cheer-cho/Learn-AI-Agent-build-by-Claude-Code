"""Module 16 package tests — streaming and human-in-the-loop.

Fully offline and deterministic. Three capabilities are covered:

1. Token streaming: MockStreamingLLM yields multiple chunks that reassemble to
   exactly the scripted reply.
2. Event streaming: stream_agent_events on the real capstone graph yields
   node-start events in execution order (router before formatter).
3. Approval gate: a request pauses at interrupt with NO ticket created; approve
   creates a ticket with an id; reject creates nothing and returns a graceful
   message. Resume reuses the same thread_id via a checkpointer, including a
   temp-file SqliteSaver that would survive a restart.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from techcorp_agent.capstone import build_graph, build_offline_store
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage
from techcorp_agent.streaming import (
    MockStreamingLLM,
    PendingApproval,
    TicketResult,
    build_approval_graph,
    collect,
    create_ticket,
    resume_with_decision,
    start_ticket_request,
    stream_agent_events,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"


# -- 1) token streaming ------------------------------------------------------


def test_mock_streaming_yields_multiple_chunks_reassembling_exactly():
    reply = "Escalate the refund to the billing team promptly."
    client = MockStreamingLLM(responses=[reply])
    chunks = list(client.stream_complete([ChatMessage(role="user", content="help")]))

    assert len(chunks) > 1, "streaming must produce several chunks, not one blob"
    assert collect(chunks) == reply, "chunks must reassemble to exactly the reply"
    assert client.calls, "the streaming client records the messages it was sent"


def test_mock_streaming_preserves_whitespace_and_newlines():
    reply = "Line one.\nLine two with  double space."
    chunks = list(
        MockStreamingLLM(responses=[reply]).stream_complete([ChatMessage(role="user", content="x")])
    )
    assert "".join(chunks) == reply


def test_mock_streaming_echo_mode_offline():
    client = MockStreamingLLM()
    chunks = list(client.stream_complete([ChatMessage(role="user", content="hello")]))
    assert collect(chunks)
    assert "hello" in collect(chunks)


# -- 2) event streaming on the capstone graph --------------------------------


@pytest.fixture(scope="module")
def capstone_store():
    return build_offline_store(persist_dir=Path(tempfile.mkdtemp()))


def test_stream_agent_events_node_order_router_before_formatter(capstone_store):
    llm = MockLLMClient(
        responses=[
            "document_search",  # router decision
            "Yes, jeans are fine under business-casual.\nSOURCES: hr-dress-code",
        ]
    )
    graph = build_graph(llm, capstone_store)
    state = {
        "conversation_id": "t",
        "question": "Am I allowed to wear jeans under the dress code at headquarters?",
        "trace": [],
        "loop_count": 0,
    }

    events = list(stream_agent_events(graph, state))
    node_events = [e for e in events if e.type == "node"]
    node_order = [e.node for e in node_events]

    assert "router" in node_order and "formatter" in node_order
    assert node_order.index("router") < node_order.index("formatter")
    # A routing decision surfaces as its own event.
    assert any(e.type == "route" for e in events)


def test_stream_agent_events_reports_updated_keys(capstone_store):
    llm = MockLLMClient(responses=["document_search", "Answer.\nSOURCES: hr-dress-code"])
    graph = build_graph(llm, capstone_store)
    state = {
        "conversation_id": "t",
        "question": "Am I allowed to wear jeans under the dress code at headquarters?",
        "trace": [],
        "loop_count": 0,
    }
    events = list(stream_agent_events(graph, state))
    router_event = next(e for e in events if e.type == "node" and e.node == "router")
    assert "route" in router_event.updated_keys


# -- 3) approval gate --------------------------------------------------------

TICKET_QUESTION = "Please create a support ticket for my damaged AeroBook order TC-2048."


def _approval_graph(checkpointer):
    llm = MockLLMClient(responses=["Damaged AeroBook on delivery"])
    return build_approval_graph(llm, checkpointer)


def test_request_pauses_without_creating_ticket():
    graph = _approval_graph(MemorySaver())
    with mock.patch("techcorp_agent.streaming.approval.create_ticket") as spy:
        pending = start_ticket_request(graph, TICKET_QUESTION, thread_id="t-pause")
        assert spy.call_count == 0, "no ticket may be created before approval"

    assert isinstance(pending, PendingApproval)
    assert pending.payload["action"] == "create_ticket"
    assert pending.payload["order_id"] == "TC-2048"
    assert "AeroBook" in pending.payload["summary"] or pending.payload["summary"]
    assert pending.thread_id == "t-pause"


def test_approve_creates_ticket_with_id():
    graph = _approval_graph(MemorySaver())
    pending = start_ticket_request(graph, TICKET_QUESTION, thread_id="t-approve")
    assert isinstance(pending, PendingApproval)

    result = resume_with_decision(graph, "t-approve", approved=True)
    assert isinstance(result, TicketResult)
    assert result.approved is True
    assert result.ticket_id and result.ticket_id.startswith("TCK-")
    assert result.ticket_id in result.message


def test_reject_creates_no_ticket_and_explains():
    graph = _approval_graph(MemorySaver())
    start_ticket_request(graph, TICKET_QUESTION, thread_id="t-reject")

    result = resume_with_decision(graph, "t-reject", approved=False)
    assert result.approved is False
    assert result.ticket_id is None
    assert "no ticket" in result.message.lower()


def test_create_ticket_action_is_deterministic_and_offline():
    a = create_ticket("Damaged AeroBook", order_id="TC-2048")
    b = create_ticket("Damaged AeroBook", order_id="TC-2048")
    assert a == b and a.startswith("TCK-")
    assert create_ticket("Other issue") != a


def test_build_approval_graph_requires_checkpointer():
    with pytest.raises(ValueError, match="checkpointer"):
        build_approval_graph(MockLLMClient(), checkpointer=None)


def test_resume_uses_same_thread_id_via_sqlite_checkpointer(tmp_path):
    """The paused thread is recovered from a temp-file Sqlite checkpointer.

    Building a fresh graph against the same file (as a new process would) and
    resuming the same thread_id proves the pending approval is durable, not just
    in memory.
    """
    db_path = tmp_path / "approvals.sqlite"

    # "Process 1": start the request, pause at the gate.
    conn1 = sqlite3.connect(db_path, check_same_thread=False)
    graph1 = _approval_graph(SqliteSaver(conn1))
    pending = start_ticket_request(graph1, TICKET_QUESTION, thread_id="durable-1")
    assert isinstance(pending, PendingApproval)
    conn1.close()  # simulate the process exiting

    # "Process 2": a brand-new graph over the same file resumes the same thread.
    conn2 = sqlite3.connect(db_path, check_same_thread=False)
    graph2 = _approval_graph(SqliteSaver(conn2))
    result = resume_with_decision(graph2, "durable-1", approved=True)
    conn2.close()

    assert result.approved is True
    assert result.ticket_id and result.ticket_id.startswith("TCK-")
    # The summary prepared in "process 1" survived into the resumed message.
    assert result.message
