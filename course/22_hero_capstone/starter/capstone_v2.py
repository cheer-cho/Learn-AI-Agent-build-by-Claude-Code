"""Module 22 lab — assemble the TechCorp Knowledge Agent v2 yourself.

Everything you need is already built and imported below — the multi-agent
supervisor (Module 18), advanced retrieval (Module 17), durable memory (Module
15), streaming and the approval gate (Module 16), safety (Module 20), and tracing
(Module 19). Your job is the CAPSTONE job: **integrate** them. v2 is not a
rewrite — you wire the finished packages together at the joints.

The gaps sit at the five integration joints (search for the marker lines and fill
them in):

    1. build the graph WITH the memory checkpointer   (durable multi-turn memory)
    2. resume the approval interrupt                  (human-in-the-loop write)
    3. run under a safety budget                       (guardrails at the boundary)
    4. capture a run with the tracer                   (observability)
    5. stream the event feed                           (live progress)

When every gap is filled (no marker lines remain), run it offline:

    TECHCORP_OFFLINE=true uv run python course/22_hero_capstone/starter/capstone_v2.py

and the tests stop skipping:

    uv run pytest course/22_hero_capstone -q

Compare your finished assembly with `techcorp_agent.capstone_v2.build_v2_graph`
— they are the same wiring. That is the point: the library graph is not magic,
it is exactly the integration you just performed.
"""

from __future__ import annotations

import tempfile

from langgraph.types import Command

from techcorp_agent.capstone_v2 import build_v2_graph, build_v2_store
from techcorp_agent.capstone_v2.graph import traced_invoke
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.safety.budget import SessionBudget
from techcorp_agent.streaming.events import INTERRUPT_KEY, stream_agent_events
from techcorp_agent.tracing import LocalTracer
from techcorp_agent.vectorstore.chroma_store import VectorStore


def build_agent(llm: LLMClient, store: VectorStore, *, db_path=None, budget=None):
    """Integration joint #1 — build the v2 graph with durable memory.

    The v2 graph must be compiled with a checkpointer so conversations (and any
    paused approval) persist across turns and restarts. `build_v2_graph` creates a
    durable SqliteSaver when you pass it a `db_path`. Passing `budget` is joint
    #3 — the safety budget the boundary node enforces.

    Return `build_v2_graph(llm, store, db_path=db_path, budget=budget)`.
    """
    raise NotImplementedError("TODO: build and return the v2 graph (joints #1 and #3).")


def ask(app, question: str, conversation_id: str = "demo") -> dict:
    """Run one question on a conversation thread and return the final state.

    The checkpointer threads history by `thread_id`, so passing the same
    `conversation_id` again continues the conversation. Invoke `app` with
    `{"question": question, "trace": []}` and the config
    `{"configurable": {"thread_id": conversation_id}}`; return the result.
    """
    raise NotImplementedError("TODO: invoke the graph with a thread_id config.")


def approve_ticket(app, question: str, conversation_id: str, *, approved: bool) -> dict:
    """Integration joint #2 — drive the approval interrupt end to end.

    The ticket node calls `interrupt(...)` BEFORE creating anything, so the first
    invoke pauses (its result carries the `INTERRUPT_KEY`). You then resume with
    the human's decision:

    1. invoke `app` with the ticket request under `config`; the graph pauses.
    2. resume with `Command(resume="approve" if approved else "reject")` under the
       SAME `config`; return that final state.
    """
    config = {"configurable": {"thread_id": conversation_id}}
    raise NotImplementedError("TODO: invoke to pause, then resume with the decision.")


def traced_run(app, question: str, conversation_id: str, tracer, llm) -> dict:
    """Integration joint #4 — capture a run with the tracer.

    `traced_invoke` reuses the Module 19 LocalTracer machinery and threads the
    conversation through the checkpointer. Return
    `traced_invoke(app, question, conversation_id=conversation_id, tracer=tracer,
    llm=llm)`.
    """
    raise NotImplementedError("TODO: capture the run with traced_invoke.")


def stream_run(app, question: str, conversation_id: str) -> list:
    """Integration joint #5 — collect the streamed event feed.

    `stream_agent_events` normalizes `graph.stream(...)` into readable
    AgentEvents. Return the list of events produced by
    `stream_agent_events(app, {"question": question, "trace": []},
    {"configurable": {"thread_id": conversation_id}})`.
    """
    raise NotImplementedError("TODO: collect the streamed AgentEvent list.")


def main() -> int:
    """Walk each integrated capability, fully offline (once the gaps are filled)."""
    store = build_v2_store()
    db = tempfile.mktemp(suffix=".sqlite")

    # Policy (supervisor -> policy specialist, advanced RAG, cited).
    llm = MockLLMClient(responses=["policy", "Up to 30 days.\nSOURCES: hr-international-remote"])
    s = ask(
        build_agent(llm, store, db_path=db), "Can an international employee work remotely?", "c1"
    )
    print(f"1) Policy route={s['route']} sources={s['sources']}")

    # Calculator (no document attribution).
    s = ask(build_agent(MockLLMClient(), store, db_path=db), "What is 17.5% of 8,400?", "c2")
    print(f"2) Calculator route={s['route']} answer={s['answer']!r}")

    # Approval gate (interrupt -> approve).
    g = build_agent(MockLLMClient(), store, db_path=db)
    s = approve_ticket(g, "Please open a support ticket for order TC-2048", "tk", approved=True)
    print(f"3) Approval created={'Created support ticket' in s['answer']}")

    # Budget hard-limit (refuse).
    g = build_agent(
        MockLLMClient(),
        store,
        db_path=db,
        budget=SessionBudget(soft_limit_usd=0.0, hard_limit_usd=0.0),
    )
    s = ask(g, "How much vacation do I get?", "bud")
    print(f"4) Budget blocked={s.get('blocked')}")

    # Tracing (captured run).
    tracer = LocalTracer(path=tempfile.mktemp(suffix=".jsonl"))
    tllm = MockLLMClient()
    s = traced_run(build_agent(tllm, store, db_path=db), "What is 2+2?", "tr", tracer, tllm)
    print(f"5) Traced answer={s['answer']!r}")

    # Streaming (event feed).
    events = stream_run(build_agent(MockLLMClient(), store, db_path=db), "What is 2+2?", "st")
    print(f"6) Streaming events={len(events)}")

    print("All integrated capabilities ran offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
