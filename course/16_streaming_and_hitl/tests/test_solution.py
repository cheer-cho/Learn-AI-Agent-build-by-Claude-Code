"""Module 16 tests — reference solution. Always runs, fully offline.

Proves the four labs work against the streaming/HITL package:

- Lab A: streaming a reply yields the exact reassembled text.
- Lab B: workflow events arrive in execution order (router before formatter).
- Lab C: the gate pauses without creating a ticket; approve creates one, reject
  does not (with a graceful message).
- Lab D: a fresh Sqlite-backed graph resumes the same thread_id.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techcorp_agent.capstone import build_graph, build_offline_store
from techcorp_agent.course_utils import import_from_path
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage
from techcorp_agent.streaming import MockStreamingLLM, PendingApproval, TicketResult

MODULE_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def solution():
    return import_from_path(
        "m16_solution_streaming_lab", MODULE_DIR / "solution" / "streaming_lab.py"
    )


@pytest.fixture(scope="module")
def store():
    import tempfile

    return build_offline_store(persist_dir=Path(tempfile.mkdtemp()))


# -- Lab A -------------------------------------------------------------------


def test_lab_a_stream_answer_returns_exact_reassembled_text(solution, capsys):
    reply = "Yes, jeans are fine under business-casual at headquarters."
    client = MockStreamingLLM(responses=[reply])
    messages = [ChatMessage(role="user", content="dress code?")]

    full = solution.stream_answer_to_cli(client, messages)
    assert full == reply, "streamed chunks must reassemble to the exact reply"
    # It streamed to the CLI (printed the text), not just returned it.
    assert reply.split()[0] in capsys.readouterr().out


# -- Lab B -------------------------------------------------------------------


def test_lab_b_events_in_execution_order(solution, store):
    llm = MockLLMClient(
        responses=["document_search", "Yes, jeans are fine.\nSOURCES: hr-dress-code"]
    )
    graph = build_graph(llm, store)
    state = {
        "conversation_id": "t",
        "question": solution.DRESS_CODE_QUESTION,
        "trace": [],
        "loop_count": 0,
    }
    events = solution.stream_workflow_events(graph, state, echo=False)
    node_order = [e.node for e in events if e.type == "node"]
    assert node_order.index("router") < node_order.index("formatter")
    assert any(e.type == "route" for e in events)


# -- Lab C -------------------------------------------------------------------


def test_lab_c_approve_creates_ticket(solution):
    result = solution.run_approval_gate(solution.TICKET_QUESTION, approve=True, echo=False)
    assert isinstance(result, TicketResult)
    assert result.approved is True
    assert result.ticket_id and result.ticket_id.startswith("TCK-")


def test_lab_c_reject_creates_no_ticket(solution):
    result = solution.run_approval_gate(solution.TICKET_QUESTION, approve=False, echo=False)
    assert result.approved is False
    assert result.ticket_id is None
    assert "no ticket" in result.message.lower()


def test_lab_c_gate_pauses_before_creating(solution):
    """start_ticket_request must return a PendingApproval (paused), not a result."""
    from langgraph.checkpoint.memory import MemorySaver

    from techcorp_agent.streaming import build_approval_graph, start_ticket_request

    graph = build_approval_graph(MockLLMClient(responses=["Damaged AeroBook"]), MemorySaver())
    pending = start_ticket_request(graph, solution.TICKET_QUESTION, "gate-pause")
    assert isinstance(pending, PendingApproval)
    assert pending.payload["order_id"] == "TC-2048"


# -- Lab D -------------------------------------------------------------------


def test_lab_d_resume_after_restart(solution):
    result = solution.resume_after_restart(solution.TICKET_QUESTION, echo=False)
    assert isinstance(result, TicketResult)
    assert result.approved is True
    assert result.ticket_id and result.ticket_id.startswith("TCK-")


def test_solution_main_runs_offline(solution):
    assert solution.main([]) == 0
