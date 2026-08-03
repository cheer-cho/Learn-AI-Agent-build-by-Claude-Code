"""Module 15 starter — give the TechCorp agent a memory.

Work through lab.md and replace each TODO. Each function raises with a pointer to
its task until you implement it, so the script never crashes with a confusing
traceback — it stops with a to-do.

Run it:
    TECHCORP_OFFLINE=true uv run python \
        course/15_memory_and_persistence/starter/memory_lab.py
Check it:
    uv run pytest course/15_memory_and_persistence -q

Everything you need already lives in the shared library — your job is to wire the
pieces together, not to reimplement them:

    from techcorp_agent.memory import (
        build_memory_graph,   # compile the capstone graph WITH a SQLite checkpointer
        ask,                  # ask(graph, question, thread_id[, user_id, preferences])
        apply_budget,         # (llm, messages, max_tokens) -> (messages, was_summarized)
        estimate_history_tokens,
        UserMemoryStore,      # remember(user_id, key, value) / recall(user_id)
    )
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

    Return ``[answer_turn_1, answer_turn_2]``.
    """
    store = build_offline_store()

    # A retrieval turn makes TWO LLM calls: the router (reply "document_search"
    # forces the retrieval path) then the grounded answer. Turn 1 uses this
    # session's scripted replies; turn 2 (after the restart) uses the next one.
    first_session = MockLLMClient(
        responses=[
            "document_search",
            "Short international remote work is capped at 30 calendar days per year.\nSOURCES: none",
        ]
    )
    second_session = MockLLMClient(
        responses=[
            "document_search",
            "Beyond 30 days you need joint approval from Legal and HR.\nSOURCES: none",
        ]
    )

    # TODO (Lab A): implement the two turns and return both answers.
    #
    #   Step 1 — build a checkpointed graph over `store`, persisting to `db_path`,
    #   and ask turn 1 on thread_id "priya-remote-work":
    #       graph = build_memory_graph(first_session, store, db_path)
    #       a1 = ask(graph, "Can I work remotely from Spain for a few weeks this autumn?",
    #                thread_id="priya-remote-work")
    #       del graph   # simulate the application exiting — nothing kept in memory
    #
    #   Step 2 — build a BRAND-NEW graph on the SAME db_path and ask the follow-up
    #   on the SAME thread_id. If memory works, "that" resolves against turn 1:
    #       graph = build_memory_graph(second_session, store, db_path)
    #       a2 = ask(graph, "What if I stay longer than that?",
    #                thread_id="priya-remote-work")
    #
    #   Then, to see the proof, print and return:
    #       print(f"Turn 1  A: {a1}")
    #       print(f"Turn 2  A: {a2}")
    #       followup_prompt = " ".join(m.content for call in second_session.calls for m in call)
    #       print("   [check] follow-up saw turn 1:",
    #             "work remotely from Spain" in followup_prompt)
    #       state = graph.get_state({"configurable": {"thread_id": "priya-remote-work"}})
    #       print("   [check] persisted messages:", len(state.values["messages"]))
    #       return [a1, a2]
    raise NotImplementedError("Lab A — build the graph, run both turns, return the answers")


def demo_summarization_under_budget() -> tuple[int, int]:
    """Lab B — show a history before and after a token budget is applied.

    Return ``(tokens_before, tokens_after)``.
    """
    history = [
        ChatMessage(
            role="user",
            content="Walk me through the whole international remote-work policy. " * 12,
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

    # TODO (Lab B): apply the token budget to `history`, print the AFTER view, and
    #   return (tokens_before, tokens_after). `apply_budget` returns
    #   (messages, was_summarized); older turns become one summary message while
    #   the recent turns stay verbatim.
    #       budgeted, was_summarized = apply_budget(
    #           summarizer, history, max_tokens=budget, keep_recent=4
    #       )
    #       print("--- AFTER (summarized to fit the budget) ---")
    #       for m in budgeted:
    #           print(f"  {m.role:9} {m.content[:60]}")
    #       tokens_after = estimate_history_tokens(budgeted)
    #       print(f"  estimated tokens: {tokens_after}  (was_summarized={was_summarized})")
    #       return tokens_before, tokens_after
    raise NotImplementedError("Lab B — call apply_budget and return the token counts")


def demo_long_term_preferences(user_db: Path, session_db: Path) -> str:
    """Lab C — store a durable fact in one session, apply it in a later one.

    Return the answer produced in the second session (its prompt carries the prefs).
    """
    store = build_offline_store()
    mock = MockLLMClient(responses=["none", "Hi Priya — happy to help."])  # general route

    # TODO (Lab C): three steps, then return the answer.
    #
    #   Step 1 — store durable facts, then close (end of session 1):
    #       store_a = UserMemoryStore(user_db)
    #       store_a.remember("priya", "department", "Engineering")
    #       store_a.remember("priya", "preferred_answer_length", "short")
    #       store_a.close()
    #
    #   Step 2 — REOPEN the store (a later session) and recall; durability means
    #   the reopened store still has the facts:
    #       store_b = UserMemoryStore(user_db)
    #       prefs = store_b.recall("priya")
    #       store_b.close()
    #
    #   Step 3 — ask on a NEW thread, passing preferences=prefs so the facts are
    #   injected into this session's prompt:
    #       graph = build_memory_graph(mock, store, session_db)
    #       answer = ask(graph, "Hi, can you help me get set up?",
    #                    thread_id="priya-day-two", user_id="priya", preferences=prefs)
    #       prompt = " ".join(m.content for call in mock.calls for m in call)
    #       print("   [check] prompt carried department:", "Engineering" in prompt)
    #       return answer
    raise NotImplementedError("Lab C — remember, recall after reopen, apply in a new session")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        print("Lab A — Checkpointed conversation")
        demo_checkpointed_conversation(tmp_path / "conversation.db")
        print("Lab B — Summarization under a budget")
        demo_summarization_under_budget()
        print("Lab C — Long-term preferences")
        demo_long_term_preferences(tmp_path / "users.db", tmp_path / "session.db")
    print("All three labs ran offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
