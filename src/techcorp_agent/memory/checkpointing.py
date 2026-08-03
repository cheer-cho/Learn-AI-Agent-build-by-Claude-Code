"""A memory-enabled TechCorp agent graph (Module 15, Lab A).

The v1 capstone (:mod:`techcorp_agent.capstone.graph`) answers one question at a
time and forgets everything the instant ``invoke`` returns: its ``AgentState``
has a single ``question`` / ``answer`` and no message history, and it compiles
with **no checkpointer**, so nothing is persisted between calls. That is fine for
a one-shot demo and wrong for a company-wide assistant employees actually talk
to.

This module adds two things *without editing a single capstone file*:

1. **A message history in the state.** :class:`MemoryAgentState` extends the idea
   of the capstone state with a ``messages`` field carrying an ``add_messages``
   reducer, so each turn *appends* to the running conversation instead of
   overwriting it.
2. **A checkpointer.** :func:`build_memory_graph` compiles the graph with a
   :class:`~langgraph.checkpoint.sqlite.SqliteSaver`, so the whole state is
   written to SQLite after every turn and can be reloaded — by the same process
   or a brand-new one — as long as the ``thread_id`` matches.

Composition, not reimplementation: the nodes here reuse the capstone's building
blocks (the RAG pipeline, the tools router, the local calculator/order tools). We
*wrap* them so that the conversation history — and any injected long-term
preferences — is prepended to the messages we actually send the LLM. That is what
makes a follow-up like "what if I stay longer than that?" resolve against the
earlier turn: the earlier turn is right there in the prompt.

The important APIs, verified against the installed versions (langgraph 1.2.10,
langgraph-checkpoint-sqlite 3.1.1):

- ``from langgraph.checkpoint.sqlite import SqliteSaver`` — construct it directly
  as ``SqliteSaver(sqlite3.connect(path, check_same_thread=False))`` and call
  ``.setup()`` once. (Its ``from_conn_string`` helper is a *context manager*,
  which would close the DB when the ``with`` block exits — no good for a graph
  that must outlive the call, so we own the connection ourselves.)
- ``graph.compile(checkpointer=saver)`` enables persistence.
- ``graph.invoke(state, config={"configurable": {"thread_id": ...}})`` threads a
  conversation; ``graph.get_state(config)`` reads the persisted state back.
"""

from __future__ import annotations

import operator
import sqlite3
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

# Reuse the capstone's route labels + tool→route map so behavior matches v1.
from techcorp_agent.capstone.graph import (  # noqa: E402  (grouped with capstone imports)
    _ORDER_ID_RE,
    _ROUTE_FOR_TOOL,
    ROUTE_GENERAL,
    ROUTE_RETRIEVAL,
)
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.memory.long_term import inject_preferences
from techcorp_agent.memory.summarization import apply_budget
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT, RAGPipeline
from techcorp_agent.schemas import ChatMessage
from techcorp_agent.tools.calculator import make_calculator_tool
from techcorp_agent.tools.orders import make_order_lookup_tool
from techcorp_agent.tools.router import keyword_route, route_question
from techcorp_agent.tools.search_docs import make_document_search_tool
from techcorp_agent.vectorstore.chroma_store import VectorStore


def _messages_reducer(
    existing: list[ChatMessage] | None, update: list[ChatMessage]
) -> list[ChatMessage]:
    """Append new messages to the running history (an ``add_messages``-style reducer).

    We keep our own small reducer (plain ``list`` concatenation) rather than
    LangGraph's ``add_messages`` so the history stays as ``ChatMessage`` objects —
    the exact type every capstone component already speaks — instead of being
    converted to LangChain message classes. Persistence works the same: the
    checkpointer serializes whatever the reducer produces.
    """
    return list(existing or []) + list(update)


class MemoryAgentState(TypedDict, total=False):
    """State for the memory graph: the capstone fields plus a conversation history.

    ``messages`` is the new, load-bearing field — an accumulating transcript with
    a reducer, so every turn appends. ``user_id`` and ``preferences`` carry the
    long-term memory (Lab C) into the prompt. The rest mirror the capstone so the
    reused nodes feel identical.
    """

    # -- conversation memory (new in Module 15) ----------------------------
    messages: Annotated[list[ChatMessage], _messages_reducer]
    thread_id: str
    user_id: str
    preferences: dict[str, str]

    # -- per-turn input / output (as in the capstone) ----------------------
    question: str
    route: str
    answer: str
    sources: list[str]
    tool_result: str
    was_summarized: bool
    trace: Annotated[list[str], operator.add]


def _trace(node: str, detail: str = "") -> list[str]:
    line = f"[node={node}]"
    if detail:
        line += f" {detail}"
    return [line]


def _history_preamble(messages: list[ChatMessage], upto: int) -> list[ChatMessage]:
    """The prior conversation, rendered as one ``system`` recap message.

    We collapse everything before the current question into a single system note
    ("Conversation so far: ...") rather than replaying raw messages, because the
    capstone's prompts are strict two-message (system + user) shapes and we want
    the history to ride *alongside* those without breaking the grounding contract.
    The recap is what makes prior turns visible to the LLM — and therefore what
    the memory tests assert on by inspecting ``mock.calls``.
    """
    prior = messages[:upto]
    if not prior:
        return []
    lines = [f"{m.role}: {m.content}" for m in prior]
    recap = "Conversation so far (most recent last):\n" + "\n".join(lines)
    return [ChatMessage(role="system", content=recap)]


def build_memory_graph(
    llm: LLMClient,
    store: VectorStore,
    db_path: str | Path,
    mcp_registry: Any | None = None,
    max_history_tokens: int = 2000,
) -> Any:
    """Build the capstone agent with SQLite-checkpointed conversation memory.

    Args:
        llm: the application LLM client (mock offline, real with a key).
        store: the vector store backing retrieval (``build_offline_store()``).
        db_path: path to the SQLite file the checkpointer persists to. The same
            path in a later process continues every conversation stored in it.
        mcp_registry: an optional connected MCP registry, exactly as the capstone
            expects; ``None`` uses the in-process local tools.
        max_history_tokens: the conversation budget. Before each LLM turn the
            history is summarized down if it would exceed this (see Lab B).

    Returns:
        A compiled LangGraph. Invoke it with
        ``config={"configurable": {"thread_id": <id>}}``; state persists to
        ``db_path`` after every turn and is reloaded on the next invoke with the
        same thread id.
    """
    pipeline = RAGPipeline(store, llm)
    calculator_tool = make_calculator_tool()
    order_tool = make_order_lookup_tool()
    doc_tool = make_document_search_tool(store)

    def _registry_has(tool_name: str) -> bool:
        if mcp_registry is None:
            return False
        try:
            return tool_name in mcp_registry.tools()
        except Exception:  # noqa: BLE001 - a broken registry must not crash routing
            return False

    # -- ingest node: fold this turn's question into the history + budget ----

    def ingest_node(state: MemoryAgentState) -> dict:
        """Append the user's question to history and apply the token budget.

        This is where short-term memory meets Lab B: after appending the new
        turn, we ask :func:`apply_budget` whether the running history is over
        ``max_history_tokens`` and, if so, summarize the older turns. The
        (possibly summarized) history is what later nodes read.
        """
        question = state["question"]
        existing = state.get("messages", [])
        history = existing + [ChatMessage(role="user", content=question)]

        trimmed, was_summarized = apply_budget(llm, history, max_history_tokens)

        update: dict = {
            # Append only the new user turn to the persisted messages; the summary
            # (if any) is applied per-turn to the prompt, not written to history.
            "messages": [ChatMessage(role="user", content=question)],
            "was_summarized": was_summarized,
            "trace": _trace("ingest", f"turns={len(history)} summarized={was_summarized}"),
        }
        # Stash the budgeted view for downstream nodes via a private key.
        update["_budgeted"] = trimmed
        return update

    def _prompt_history(state: MemoryAgentState) -> list[ChatMessage]:
        """The history-recap messages to prepend to this turn's LLM prompt.

        Uses the budgeted view produced by ``ingest_node`` (so it reflects any
        summarization), drops the just-appended current question (the nodes add
        the question themselves), and injects any long-term preferences in front.
        """
        budgeted: list[ChatMessage] = state.get("_budgeted") or state.get("messages", [])
        # The last message is the current question; recap everything before it.
        recap = _history_preamble(budgeted, upto=max(0, len(budgeted) - 1))
        return inject_preferences(recap, state.get("preferences", {}))

    # -- router node --------------------------------------------------------

    def router_node(state: MemoryAgentState) -> dict:
        question = state["question"]
        tools = [doc_tool, calculator_tool, order_tool]
        try:
            tool_name = route_question(question, llm, tools)
        except Exception:  # noqa: BLE001 - a router LLM failure degrades to keywords
            tool_name = keyword_route(question, tools)
        route = _ROUTE_FOR_TOOL.get(tool_name, ROUTE_GENERAL)
        return {"route": route, "trace": _trace("router", f"tool={tool_name} route={route}")}

    def route_selector(state: MemoryAgentState) -> str:
        return state.get("route", ROUTE_GENERAL)

    # -- retrieval node (history-aware) ------------------------------------

    def retrieval_node(state: MemoryAgentState) -> dict:
        """Grounded answer, with the conversation history prepended to the prompt.

        We call the pipeline's retrieval and prompt builder directly (reusing its
        grounding contract) and then splice the history recap between the system
        rules and the context+question. That single change is what turns a
        stateless RAG turn into a conversational one.
        """
        question = state["question"]
        chunks = pipeline.retrieve(question)
        if not chunks:
            return {
                "answer": ABSTENTION_TEXT,
                "sources": [],
                "trace": _trace("retrieval", "chunks=0 abstained=True"),
            }
        base = pipeline.build_messages(question, chunks)
        # base == [system_rules, user(context+question)]; insert history after rules.
        messages = [base[0], *_prompt_history(state), *base[1:]]
        result = llm.complete(messages, temperature=0.0)
        from techcorp_agent.rag.pipeline import parse_answer

        answer_text, sources = parse_answer(result.content)
        supplied = {r.chunk.doc_id for r in chunks}
        sources = [s for s in sources if s in supplied]
        abstained = ABSTENTION_TEXT.lower() in answer_text.lower()
        if abstained:
            sources = []
        return {
            "answer": answer_text,
            "sources": sources,
            "trace": _trace("retrieval", f"chunks={len(chunks)} abstained={abstained}"),
        }

    # -- calculator node ----------------------------------------------------

    def calculator_node(state: MemoryAgentState) -> dict:
        question = state["question"]
        if _registry_has("calculator.add"):
            from techcorp_agent.capstone.graph import _try_mcp_calculator

            value = _try_mcp_calculator(mcp_registry, question)
            if value is not None:
                return {
                    "tool_result": value,
                    "trace": _trace("calculator", f"backend=mcp result={value}"),
                }
        tool_result = calculator_tool.run({"expression": question})
        text = tool_result.output if tool_result.ok else (tool_result.error or "calculation failed")
        return {"tool_result": text, "trace": _trace("calculator", f"ok={tool_result.ok}")}

    # -- orders node --------------------------------------------------------

    def orders_node(state: MemoryAgentState) -> dict:
        question = state["question"]
        match = _ORDER_ID_RE.search(question)
        if not match:
            return {
                "tool_result": (
                    "I could not find an order id in your question. Order ids look "
                    "like TC-1234 — please include one."
                ),
                "trace": _trace("orders", "reason=no_order_id"),
            }
        order_id = match.group(0).upper()
        if _registry_has("orders.get_order_status"):
            from techcorp_agent.capstone.graph import _try_mcp_order

            ok, text = _try_mcp_order(mcp_registry, order_id)
        else:
            result = order_tool.run({"order_id": order_id})
            ok = result.ok
            text = result.output if result.ok else (result.error or "order lookup failed")
        return {"tool_result": text, "trace": _trace("orders", f"order={order_id} ok={ok}")}

    # -- general node (history-aware) --------------------------------------

    def general_node(state: MemoryAgentState) -> dict:
        question = state["question"]
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are TechCorp's internal assistant. Answer the user's "
                    "general request briefly and helpfully. This is not a "
                    "company-policy question, so do not cite documents."
                ),
            ),
            *_prompt_history(state),
            ChatMessage(role="user", content=question),
        ]
        try:
            reply = llm.complete(messages, temperature=0.0).content
        except Exception as exc:  # noqa: BLE001 - an LLM failure is data, not a crash
            reply = f"I'm unable to answer that right now ({exc})."
        return {"tool_result": reply, "trace": _trace("general", f"chars={len(reply)}")}

    # -- formatter node -----------------------------------------------------

    def formatter_node(state: MemoryAgentState) -> dict:
        """Finalize the answer and append it to the persisted history."""
        route = state.get("route", ROUTE_GENERAL)
        if route == ROUTE_RETRIEVAL:
            answer = state.get("answer", "") or ABSTENTION_TEXT
            sources = state.get("sources", [])
        else:
            answer = state.get("tool_result", "") or "I don't have a result for that."
            if route == "calculator":
                answer = f"The result is {answer}."
            sources = []
        return {
            "answer": answer,
            "sources": sources,
            # Record the assistant turn so the next question sees it in history.
            "messages": [ChatMessage(role="assistant", content=answer)],
            "trace": _trace("formatter", f"route={route} sources={sources}"),
        }

    # -- wiring -------------------------------------------------------------

    graph = StateGraph(MemoryAgentState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("router", router_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("calculator", calculator_node)
    graph.add_node("orders", orders_node)
    graph.add_node("general", general_node)
    graph.add_node("formatter", formatter_node)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "router")
    graph.add_conditional_edges(
        "router",
        route_selector,
        {
            ROUTE_RETRIEVAL: "retrieval",
            "calculator": "calculator",
            "orders": "orders",
            ROUTE_GENERAL: "general",
        },
    )
    graph.add_edge("retrieval", "formatter")
    graph.add_edge("calculator", "formatter")
    graph.add_edge("orders", "formatter")
    graph.add_edge("general", "formatter")
    graph.add_edge("formatter", END)

    checkpointer = _make_checkpointer(db_path)
    return graph.compile(checkpointer=checkpointer)


def _make_checkpointer(db_path: str | Path) -> SqliteSaver:
    """Construct a SqliteSaver that owns a long-lived connection to ``db_path``.

    ``check_same_thread=False`` lets the graph's worker thread reach the same
    connection; ``.setup()`` creates the checkpoint tables on first use and is a
    no-op afterwards, so reopening the same file continues the conversation.

    We hand the saver a serializer that *explicitly allows* our ``ChatMessage``
    type in the persisted checkpoint. langgraph 1.2 warns (and will one day
    refuse) when it deserializes an unregistered custom type from disk; naming
    the module here makes the round-trip safe and silent.
    """
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    serde = JsonPlusSerializer(allowed_msgpack_modules=[("techcorp_agent.schemas", "ChatMessage")])
    saver = SqliteSaver(conn, serde=serde)
    saver.setup()
    return saver


def ask(
    graph: Any,
    question: str,
    thread_id: str,
    user_id: str | None = None,
    preferences: dict[str, str] | None = None,
) -> str:
    """Ask one question on a conversation thread and return the answer text.

    This is the conversation helper the CLI-style flow (and Lab A) uses: it hides
    the LangGraph ``config`` plumbing and the fact that history is threaded for
    you by the checkpointer. Because the graph was compiled with a checkpointer,
    passing the same ``thread_id`` again continues the conversation — the prior
    turns are reloaded from SQLite and prepended to the prompt automatically.

    Args:
        preferences: durable user facts (from :meth:`UserMemoryStore.recall`) to
            inject into this turn's prompt. Pass them explicitly so long-term
            memory (Lab C) applies even in a fresh session on a new thread.
    """
    config = {"configurable": {"thread_id": thread_id}}
    initial: dict = {"question": question, "trace": []}
    if user_id is not None:
        initial["user_id"] = user_id
    if preferences:
        initial["preferences"] = preferences
    result = graph.invoke(initial, config=config)
    return result.get("answer", "")
