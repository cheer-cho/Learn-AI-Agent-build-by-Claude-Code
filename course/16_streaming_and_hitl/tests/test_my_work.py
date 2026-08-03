"""Module 16 tests — your starter implementation.

These auto-skip while starter/streaming_lab.py still contains TODO markers.
Once you finish the four labs, they run and become your completion gate:

    uv run pytest course/16_streaming_and_hitl -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techcorp_agent.capstone import build_graph, build_offline_store
from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage
from techcorp_agent.streaming import MockStreamingLLM, TicketResult

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/streaming_lab.py still contains TODO markers — finish the labs first",
)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m16_starter_streaming_lab", STARTER_DIR / "streaming_lab.py")


@pytest.fixture(scope="module")
def store():
    import tempfile

    return build_offline_store(persist_dir=Path(tempfile.mkdtemp()))


def test_lab_a_stream_answer_returns_exact_reassembled_text(my_work):
    reply = "Yes, jeans are fine under business-casual at headquarters."
    client = MockStreamingLLM(responses=[reply])
    full = my_work.stream_answer_to_cli(
        client, [ChatMessage(role="user", content="dress code?")], echo=False
    )
    assert full == reply


def test_lab_b_events_in_execution_order(my_work, store):
    llm = MockLLMClient(
        responses=["document_search", "Yes, jeans are fine.\nSOURCES: hr-dress-code"]
    )
    graph = build_graph(llm, store)
    state = {
        "conversation_id": "t",
        "question": my_work.DRESS_CODE_QUESTION,
        "trace": [],
        "loop_count": 0,
    }
    events = my_work.stream_workflow_events(graph, state, echo=False)
    node_order = [e.node for e in events if e.type == "node"]
    assert node_order.index("router") < node_order.index("formatter")


def test_lab_c_approve_and_reject(my_work):
    approved = my_work.run_approval_gate(my_work.TICKET_QUESTION, approve=True, echo=False)
    assert isinstance(approved, TicketResult)
    assert approved.approved is True and approved.ticket_id

    rejected = my_work.run_approval_gate(my_work.TICKET_QUESTION, approve=False, echo=False)
    assert rejected.approved is False and rejected.ticket_id is None


def test_lab_d_resume_after_restart(my_work):
    result = my_work.resume_after_restart(my_work.TICKET_QUESTION, echo=False)
    assert result.approved is True
    assert result.ticket_id and result.ticket_id.startswith("TCK-")
