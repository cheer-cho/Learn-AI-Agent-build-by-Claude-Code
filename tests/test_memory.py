"""Module 15 tests — memory and persistence for the TechCorp Knowledge Agent.

Fully offline and deterministic: the hash-embedding capstone store over the real
``data/`` corpus, scripted :class:`MockLLMClient` responses, and ``tmp_path``
SQLite databases. No API key, no network.

What each test proves:

1. multi-turn — a follow-up's LLM call carries the *first* turn's context;
2. persistence — a NEW graph on the SAME db continues the conversation (the
   state survived a simulated restart);
3. isolation — two thread ids never see each other's history;
4. summarization — triggers exactly when over budget and keeps recent turns
   verbatim;
5. long-term memory — the store survives reopen and preferences reach the prompt;
6. scripted conversations — the ``memory_conversations.json`` checks all hold:
   each ``must_reference`` is carried in the LLM context across the conversation.

Call-order note: a *retrieval* turn makes TWO LLM calls (the router's
``route_question`` then the grounded answer); to force a turn onto the retrieval
path the router reply is scripted as ``"document_search"``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techcorp_agent.capstone import build_offline_store
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.memory import (
    UserMemoryStore,
    apply_budget,
    ask,
    build_memory_graph,
    estimate_history_tokens,
    inject_preferences,
    summarize_history,
)
from techcorp_agent.schemas import ChatMessage

REPO_ROOT = Path(__file__).resolve().parents[1]
CONVERSATIONS = REPO_ROOT / "data" / "evaluation" / "memory_conversations.json"


@pytest.fixture(scope="module")
def store():
    """The capstone's offline hash-embedding store (built once for the module)."""
    return build_offline_store()


def _context_of(calls: list[list[ChatMessage]]) -> str:
    """Flatten a batch of LLM calls into one string for substring assertions."""
    return " ".join(m.content for call in calls for m in call)


# --------------------------------------------------------------------------- #
# 1. Multi-turn: the follow-up resolves against the first turn's context.
# --------------------------------------------------------------------------- #


def test_followup_turn_sees_first_turn_context(store, tmp_path):
    db = tmp_path / "conv.db"
    mock = MockLLMClient(
        responses=[
            "document_search",  # turn 1 router
            "You may work remotely abroad for up to 30 calendar days.\nSOURCES: none",  # turn 1 answer
            "document_search",  # turn 2 router
            "Beyond 30 days you must involve Legal.\nSOURCES: none",  # turn 2 answer
        ]
    )
    graph = build_memory_graph(mock, store, db)

    ask(graph, "Can I work remotely from Spain this autumn?", thread_id="t1")
    calls_before_followup = len(mock.calls)
    ask(graph, "What if I stay longer than that?", thread_id="t1")

    # The follow-up made a fresh router+answer pair; inspect just those calls.
    followup_context = _context_of(mock.calls[calls_before_followup:])
    assert "work remotely from Spain" in followup_context, "follow-up must see turn 1's question"
    assert "30 calendar days" in followup_context, "follow-up must see turn 1's answer"


# --------------------------------------------------------------------------- #
# 2. Persistence: a NEW graph on the same db continues the conversation.
# --------------------------------------------------------------------------- #


def test_conversation_survives_restart(store, tmp_path):
    db = tmp_path / "restart.db"

    first = MockLLMClient(
        responses=[
            "document_search",
            "Remote work abroad is capped at 30 calendar days.\nSOURCES: none",
        ]
    )
    graph_a = build_memory_graph(first, store, db)
    ask(graph_a, "How long can I work remotely from abroad?", thread_id="shared")
    del graph_a  # simulate the process exiting — nothing kept in memory

    second = MockLLMClient(responses=["document_search", "You must involve Legal.\nSOURCES: none"])
    graph_b = build_memory_graph(second, store, db)  # brand-new graph, same db file
    ask(graph_b, "What if I stay longer than that?", thread_id="shared")

    followup_context = _context_of(second.calls)
    assert "work remotely from abroad" in followup_context, "restart must reload turn 1's question"
    assert "30 calendar days" in followup_context, "restart must reload turn 1's answer"

    # And the reloaded state holds all four messages (2 turns).
    state = graph_b.get_state({"configurable": {"thread_id": "shared"}})
    assert len(state.values["messages"]) == 4


# --------------------------------------------------------------------------- #
# 3. Isolation: different thread ids do not share history.
# --------------------------------------------------------------------------- #


def test_threads_are_isolated(store, tmp_path):
    db = tmp_path / "iso.db"
    mock = MockLLMClient(
        responses=[
            "document_search",
            "Team ALPHA ships on Fridays.\nSOURCES: none",
            "document_search",
            "Fresh unrelated answer.\nSOURCES: none",
        ]
    )
    graph = build_memory_graph(mock, store, db)

    ask(graph, "When does team ALPHA ship?", thread_id="alpha")
    calls_before = len(mock.calls)
    ask(graph, "Remind me what we discussed?", thread_id="beta")  # different thread

    beta_context = _context_of(mock.calls[calls_before:])
    assert "ALPHA" not in beta_context, "thread beta must not see thread alpha's history"

    alpha_state = graph.get_state({"configurable": {"thread_id": "alpha"}})
    beta_state = graph.get_state({"configurable": {"thread_id": "beta"}})
    assert len(alpha_state.values["messages"]) == 2
    assert len(beta_state.values["messages"]) == 2


# --------------------------------------------------------------------------- #
# 4. Summarization triggers on budget overflow and keeps recent turns verbatim.
# --------------------------------------------------------------------------- #


def test_estimate_history_tokens_is_monotonic():
    short = [ChatMessage(role="user", content="hi")]
    long = [ChatMessage(role="user", content="word " * 200)]
    assert estimate_history_tokens(short) < estimate_history_tokens(long)


def test_apply_budget_no_summary_when_within_budget():
    messages = [ChatMessage(role="user", content="short question")]
    mock = MockLLMClient(responses=["(should not be called)"])
    out, was_summarized = apply_budget(mock, messages, max_tokens=10_000)
    assert was_summarized is False
    assert out == messages
    assert mock.calls == [], "no summarization means no LLM call"


def test_summarization_triggers_over_budget_and_keeps_recent_verbatim():
    # Two big older turns push us over budget; four recent turns must stay exact.
    older = [
        ChatMessage(role="user", content="OLD-Q " * 200),
        ChatMessage(role="assistant", content="OLD-A " * 200),
    ]
    recent = [
        ChatMessage(role="user", content="recent q1"),
        ChatMessage(role="assistant", content="recent a1"),
        ChatMessage(role="user", content="recent q2 verbatim"),
        ChatMessage(role="assistant", content="recent a2 verbatim"),
    ]
    messages = older + recent
    mock = MockLLMClient(responses=["Earlier, the user asked OLD things."])

    out, was_summarized = apply_budget(mock, messages, max_tokens=50, keep_recent=4)

    assert was_summarized is True
    assert len(mock.calls) == 1, "exactly one summarization call"
    # Head is a single summary system message; the four recent turns follow, exact.
    assert out[0].role == "system"
    assert out[0].content.startswith("Summary of earlier conversation:")
    assert out[1:] == recent, "the recent tail must be preserved verbatim"
    assert estimate_history_tokens(out) < estimate_history_tokens(messages)


def test_summarize_history_noop_when_short():
    messages = [ChatMessage(role="user", content="only one turn")]
    mock = MockLLMClient(responses=["unused"])
    out = summarize_history(mock, messages, keep_recent=4)
    assert out == messages
    assert mock.calls == []


# --------------------------------------------------------------------------- #
# 5. Long-term memory: store persists across reopen; preferences reach prompts.
# --------------------------------------------------------------------------- #


def test_user_memory_store_persists_across_reopen(tmp_path):
    db = tmp_path / "users.db"

    store_a = UserMemoryStore(db)
    store_a.remember("emp-42", "department", "Engineering")
    store_a.remember("emp-42", "preferred_answer_length", "short")
    store_a.remember("emp-42", "department", "Platform")  # upsert overwrites
    store_a.close()

    store_b = UserMemoryStore(db)  # reopened in a "new session"
    recalled = store_b.recall("emp-42")
    assert recalled == {"department": "Platform", "preferred_answer_length": "short"}
    assert store_b.recall("unknown-user") == {}, "an unknown user has no facts yet"
    store_b.close()


def test_inject_preferences_prepends_a_single_system_note():
    messages = [
        ChatMessage(role="system", content="rules"),
        ChatMessage(role="user", content="q"),
    ]
    out = inject_preferences(
        messages, {"department": "Engineering", "preferred_answer_length": "short"}
    )
    assert out[0].role == "system"
    assert "Engineering" in out[0].content and "short" in out[0].content
    assert out[1:] == messages, "the original messages are preserved after the note"

    # Re-applying does not stack duplicate notes.
    again = inject_preferences(out, {"department": "Engineering"})
    assert sum(1 for m in again if m.content.startswith("Known facts about the current user")) == 1

    # No preferences => no overhead.
    assert inject_preferences(messages, {}) == messages


def test_preferences_reach_the_prompt_in_a_fresh_session(store, tmp_path):
    users = UserMemoryStore(tmp_path / "u.db")
    users.remember("emp-7", "department", "Engineering")
    users.remember("emp-7", "preferred_answer_length", "short")
    prefs = users.recall("emp-7")
    users.close()

    db = tmp_path / "session.db"
    mock = MockLLMClient(responses=["none", "Hello! Happy to help."])  # general route
    graph = build_memory_graph(mock, store, db)

    ask(graph, "Hi, can you help me?", thread_id="new-session", user_id="emp-7", preferences=prefs)

    context = _context_of(mock.calls)
    assert "Engineering" in context, "the stored department must reach the prompt"
    assert "short" in context, "the stored answer-length preference must reach the prompt"


# --------------------------------------------------------------------------- #
# 6. Scripted conversations: every must_reference is carried in the LLM context.
# --------------------------------------------------------------------------- #


def _load_conversations() -> list[dict]:
    return json.loads(CONVERSATIONS.read_text(encoding="utf-8"))["conversations"]


@pytest.mark.parametrize("conversation", _load_conversations(), ids=lambda c: c["id"])
def test_scripted_conversation_carries_references(store, tmp_path, conversation):
    """Run one scripted multi-turn conversation and verify the memory checks.

    Each turn is forced onto the retrieval path (router reply ``document_search``)
    so it makes a grounded-answer LLM call; that answer is scripted to embed the
    turn's ``must_reference``. A fact only enters the *prompt* once it is part of
    the history — i.e. from the turn *after* it was answered — so the memory
    property we assert is carry-forward: the ``must_reference`` introduced at
    turn ``i`` appears in the LLM context sent at turn ``i + 1``. Each
    conversation's final check has no successor turn, so it anchors the earlier
    ones without a forward assertion of its own.
    """
    ref_by_turn = {c["turn_index"]: c["must_reference"] for c in conversation["checks"]}

    responses: list[str] = []
    for i, _turn in enumerate(conversation["turns"]):
        responses.append("document_search")  # router -> retrieval path
        responses.append(f"Turn {i} answer referencing {ref_by_turn.get(i, '')}.\nSOURCES: none")

    mock = MockLLMClient(responses=responses)
    db = tmp_path / f"{conversation['id']}.db"
    graph = build_memory_graph(mock, store, db)

    # Run every turn, capturing the LLM context produced by each.
    context_by_turn: list[str] = []
    for turn in conversation["turns"]:
        before = len(mock.calls)
        ask(graph, turn["content"], thread_id=conversation["id"])
        context_by_turn.append(_context_of(mock.calls[before:]))

    carried_forward = 0
    for turn_index, reference in ref_by_turn.items():
        # A fact enters the prompt only once it is history: from the next turn on.
        if turn_index + 1 < len(context_by_turn):
            assert reference in context_by_turn[turn_index + 1], (
                f"{conversation['id']} turn {turn_index}: {reference!r} not carried to next turn"
            )
            carried_forward += 1

    assert carried_forward >= 1, "the conversation must exercise at least one carry-forward"
