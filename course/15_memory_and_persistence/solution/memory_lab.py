"""Module 15 solution — memory and persistence for the TechCorp agent.

Reference implementation. Runs fully offline (scripted mock LLM, temp SQLite
databases) so it is deterministic:

    TECHCORP_OFFLINE=true uv run python \
        course/15_memory_and_persistence/solution/memory_lab.py

Three demonstrations, one per lab:

- Lab A — a checkpointed conversation: a follow-up resolves against an earlier
  turn, and the conversation survives a simulated restart (a brand-new graph on
  the same SQLite file).
- Lab B — summarization under a token budget: the same history printed before
  and after the budget is applied, so you can *see* fidelity traded for budget.
- Lab C — long-term preferences: a durable user fact stored in one session is
  applied in a later, separate session on a new thread.

The heavy lifting lives in the shared library (``techcorp_agent.memory``); this
script is the thin, readable driver that shows the pieces working together. The
lab's ``starter/memory_lab.py`` is this file with the key steps gapped out.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from techcorp_agent.capstone import build_offline_store
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.memory import (
    UserMemoryStore,
    apply_budget,
    ask,
    build_memory_graph,
    estimate_history_tokens,
)
from techcorp_agent.schemas import ChatMessage


def demo_checkpointed_conversation(db_path: Path) -> list[str]:
    """Lab A — a two-turn conversation that remembers, then survives a restart.

    Returns the two answer strings so the caller (and the test) can check them.
    """
    store = build_offline_store()

    # A retrieval turn makes TWO LLM calls: the router (reply "document_search"
    # forces the retrieval path) then the grounded answer.
    first_session = MockLLMClient(
        responses=[
            "document_search",
            "Short international remote work is capped at 30 calendar days per year.\nSOURCES: none",
        ]
    )
    graph = build_memory_graph(first_session, store, db_path)

    a1 = ask(
        graph,
        "Can I work remotely from Spain for a few weeks this autumn?",
        thread_id="priya-remote-work",
    )
    print("Turn 1  Q: Can I work remotely from Spain for a few weeks this autumn?")
    print(f"        A: {a1}\n")

    # Simulate the process exiting: drop the graph entirely.
    del graph

    # A brand-new graph on the SAME db file continues the conversation. The
    # follow-up ("that") only makes sense because turn 1 was reloaded from SQLite.
    second_session = MockLLMClient(
        responses=[
            "document_search",
            "Beyond 30 days you need joint approval from Legal and HR.\nSOURCES: none",
        ]
    )
    graph_after_restart = build_memory_graph(second_session, store, db_path)
    a2 = ask(
        graph_after_restart,
        "What if I stay longer than that?",
        thread_id="priya-remote-work",
    )
    print("   (application restarted — new graph, same SQLite file)")
    print("Turn 2  Q: What if I stay longer than that?")
    print(f"        A: {a2}\n")

    # Show that the earlier turn actually reached the LLM on the follow-up.
    followup_prompt = " ".join(m.content for call in second_session.calls for m in call)
    saw_history = "work remotely from Spain" in followup_prompt
    print(f"   [check] follow-up prompt contained turn 1's question: {saw_history}")

    state = graph_after_restart.get_state({"configurable": {"thread_id": "priya-remote-work"}})
    print(f"   [check] persisted messages in thread: {len(state.values['messages'])}\n")
    return [a1, a2]


def demo_summarization_under_budget() -> tuple[int, int]:
    """Lab B — show a history before and after a token budget is applied.

    Returns ``(tokens_before, tokens_after)`` so the shrink is checkable.
    """
    # A long-running conversation: two big early turns plus recent short ones.
    history = [
        ChatMessage(
            role="user", content="Walk me through the whole international remote-work policy. " * 12
        ),
        ChatMessage(role="assistant", content="Here is the full policy, section by section. " * 12),
        ChatMessage(role="user", content="Got it. How much advance notice do I need?"),
        ChatMessage(
            role="assistant", content="At least 60 days advance notice via the request form."
        ),
        ChatMessage(role="user", content="And who approves stays over 30 days?"),
        ChatMessage(role="assistant", content="Joint approval from Legal and HR."),
    ]
    budget = 120  # tokens; deliberately small so the older turns overflow it

    print("--- BEFORE (full history) ---")
    for m in history:
        print(f"  {m.role:9} {m.content[:60]}{'…' if len(m.content) > 60 else ''}")
    tokens_before = estimate_history_tokens(history)
    print(f"  estimated tokens: {tokens_before}  (budget: {budget})\n")

    # The scripted summary stands in for what a real model would write.
    summarizer = MockLLMClient(
        responses=[
            "Earlier, the user asked for a full walkthrough of the international "
            "remote-work policy and received a section-by-section explanation."
        ]
    )
    budgeted, was_summarized = apply_budget(summarizer, history, max_tokens=budget, keep_recent=4)

    print("--- AFTER (summarized to fit the budget) ---")
    for m in budgeted:
        print(f"  {m.role:9} {m.content[:60]}{'…' if len(m.content) > 60 else ''}")
    tokens_after = estimate_history_tokens(budgeted)
    print(f"  estimated tokens: {tokens_after}  (was_summarized={was_summarized})")
    print("  note: the 4 most recent turns are kept verbatim; older turns became one summary.\n")
    return tokens_before, tokens_after


def demo_long_term_preferences(user_db: Path, session_db: Path) -> str:
    """Lab C — store a durable fact in one session, apply it in a later one.

    Returns the answer produced in the second session (its prompt carries the
    preferences), so the caller can confirm they were applied.
    """
    # Session 1: learn and persist facts about the employee.
    store_a = UserMemoryStore(user_db)
    store_a.remember("priya", "department", "Engineering")
    store_a.remember("priya", "preferred_answer_length", "short")
    store_a.close()
    print("Session 1: stored department=Engineering, preferred_answer_length=short\n")

    # Session 2 (later, separate): recall and apply the facts on a NEW thread.
    store_b = UserMemoryStore(user_db)  # reopened — proves durability
    prefs = store_b.recall("priya")
    store_b.close()
    print(f"Session 2: recalled preferences {prefs}")

    store = build_offline_store()
    mock = MockLLMClient(responses=["none", "Hi Priya — happy to help."])  # general route
    graph = build_memory_graph(mock, store, session_db)
    answer = ask(
        graph,
        "Hi, can you help me get set up?",
        thread_id="priya-day-two",
        user_id="priya",
        preferences=prefs,
    )
    prompt = " ".join(m.content for call in mock.calls for m in call)
    print(f"        A: {answer}")
    print(f"   [check] prompt carried department: {'Engineering' in prompt}")
    print(f"   [check] prompt carried length preference: {'short' in prompt}\n")
    return answer


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        print("=" * 70)
        print("Lab A — Checkpointed conversation (memory + restart)")
        print("=" * 70)
        demo_checkpointed_conversation(tmp_path / "conversation.db")

        print("=" * 70)
        print("Lab B — Summarization under a token budget")
        print("=" * 70)
        demo_summarization_under_budget()

        print("=" * 70)
        print("Lab C — Long-term preferences across sessions")
        print("=" * 70)
        demo_long_term_preferences(tmp_path / "users.db", tmp_path / "session.db")

    print("All three labs ran offline. See lab.md for the guided walkthrough.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
