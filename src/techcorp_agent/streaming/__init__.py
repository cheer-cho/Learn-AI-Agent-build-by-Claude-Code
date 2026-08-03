"""Streaming and human-in-the-loop (Module 16).

Two additive capabilities the capstone agent did not have, layered on top of the
existing code without editing it:

- **Token streaming** (``token_stream``): deliver a reply chunk by chunk so a CLI
  never looks frozen. ``StreamingLLM`` is a small protocol with a deterministic
  offline mock and a live OpenAI implementation; ``collect`` reassembles chunks.
- **Event streaming** (``events``): normalize ``graph.stream(...)`` into readable
  ``AgentEvent`` records — which node ran, which route was chosen — for a CLI now
  and Server-Sent Events later (Module 21).
- **Approval gate** (``approval``): a human-in-the-loop LangGraph that pauses
  before a *write* action (create a support ticket) via ``interrupt()`` and
  resumes on a human decision, backed by a checkpointer (Module 15).
"""

from techcorp_agent.streaming.approval import (
    ACTION_CREATE_TICKET,
    ApprovalState,
    PendingApproval,
    TicketResult,
    build_approval_graph,
    create_ticket,
    resume_with_decision,
    start_ticket_request,
)
from techcorp_agent.streaming.events import (
    INTERRUPT_KEY,
    AgentEvent,
    stream_agent_events,
)
from techcorp_agent.streaming.token_stream import (
    MockStreamingLLM,
    OpenAIStreamingClient,
    StreamingLLM,
    collect,
)

__all__ = [
    # token streaming
    "StreamingLLM",
    "MockStreamingLLM",
    "OpenAIStreamingClient",
    "collect",
    # event streaming
    "AgentEvent",
    "stream_agent_events",
    "INTERRUPT_KEY",
    # approval / HITL
    "ACTION_CREATE_TICKET",
    "ApprovalState",
    "PendingApproval",
    "TicketResult",
    "build_approval_graph",
    "create_ticket",
    "start_ticket_request",
    "resume_with_decision",
]
