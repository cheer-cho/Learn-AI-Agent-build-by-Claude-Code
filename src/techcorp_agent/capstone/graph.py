"""The TechCorp Knowledge Agent v1 graph — the mid-course capstone wiring.

This module is the point of Module 14: it *composes* the components built in
Modules 02-13 into one LangGraph, and reimplements none of them. The pieces:

- routing            -> ``techcorp_agent.tools.router`` (LLM choice + the
                        deterministic ``keyword_route`` fallback);
- grounded retrieval -> ``techcorp_agent.rag.RAGPipeline`` (cite sources, abstain
                        when the evidence is insufficient);
- calculator         -> the ``calculator.*`` MCP tool when a registry is
                        available, else the local ``calculator`` tool;
- orders             -> the ``orders.get_order_status`` MCP tool, degrading to a
                        clear "order system unavailable" answer when it is not;
- general            -> a plain LLM reply for greetings / open questions.

Architecture (adapted from the Module 14 spec, with the real node names)::

    START -> router --route--> retrieval  -\
                            -> calculator  -+-> formatter -> END
                            -> orders      -/
                            -> general    -/

Two invariants the spec insists on, enforced here:

1. **Graceful degradation.** No node ever raises past its own boundary. A down
   MCP server, an unknown order, or a missing tool becomes a clean answer, never
   a traceback (the pattern from Modules 11 and 13).
2. **Honest formatting.** The formatter never dresses a calculator or order
   result up as if it came from the document corpus; only the retrieval node
   carries ``sources``.

Every node appends a structured line to ``state["trace"]`` (Module 10's
observability reducer), so dev mode and the tests can read exactly what happened.

The graph is compiled by :func:`build_graph`; it runs fully offline with the
mock LLM and a hash-embedding store, and the MCP routes fall back to local tools
whenever ``mcp_registry`` is ``None`` or a server is down.
"""

from __future__ import annotations

import re
from typing import Any

from langgraph.graph import END, START, StateGraph

from techcorp_agent.capstone.state import AgentState
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT, RAGPipeline
from techcorp_agent.schemas import ChatMessage
from techcorp_agent.tools.calculator import make_calculator_tool
from techcorp_agent.tools.orders import make_order_lookup_tool
from techcorp_agent.tools.router import keyword_route, route_question
from techcorp_agent.tools.search_docs import make_document_search_tool
from techcorp_agent.vectorstore.chroma_store import VectorStore

# The four capability routes. These are graph-level labels; the tools router
# speaks tool names, so ``_ROUTE_FOR_TOOL`` translates one into the other.
ROUTE_RETRIEVAL = "retrieval"
ROUTE_CALCULATOR = "calculator"
ROUTE_ORDERS = "orders"
ROUTE_GENERAL = "general"

_ROUTE_FOR_TOOL = {
    "document_search": ROUTE_RETRIEVAL,
    "calculator": ROUTE_CALCULATOR,
    "order_lookup": ROUTE_ORDERS,
    # "none" and anything unexpected fall through to the general LLM node.
}

# Namespaced MCP tool names (Module 13). We prefer these when a registry is up.
MCP_CALCULATOR_ADD = "calculator.add"
MCP_ORDERS_STATUS = "orders.get_order_status"

_ORDER_ID_RE = re.compile(r"\bTC-\d{3,}\b", re.IGNORECASE)


def _trace(node: str, detail: str = "") -> list[str]:
    """One structured trace line as a single-item list for the reducer."""
    line = f"[node={node}]"
    if detail:
        line += f" {detail}"
    return [line]


def build_graph(
    llm: LLMClient,
    store: VectorStore,
    mcp_registry: Any | None = None,
    max_loops: int = 3,
) -> Any:
    """Build and compile the capstone graph.

    Args:
        llm: the application LLM client (mock offline, real with a key).
        store: the vector store backing retrieval and the document-search tool.
        mcp_registry: a connected, **synchronous** MCP registry — i.e. a
            :class:`~techcorp_agent.capstone.mcp_bridge.SyncMCPRegistry` exposing
            ``tools()`` and ``call(name, args) -> CallToolResult`` — or ``None``
            to use the local calculator/order tools instead. When a registry is
            given but a needed server is down, the affected node degrades to the
            local tool (calculator) or a clear unavailable message (orders)
            rather than crashing.
        max_loops: hard cap on retrieval retries; a retry can never push
            ``loop_count`` past this, so the graph is provably finite.

    Returns:
        A compiled LangGraph whose ``.invoke(state)`` returns the final merged
        ``AgentState``.
    """
    pipeline = RAGPipeline(store, llm)
    calculator_tool = make_calculator_tool()
    order_tool = make_order_lookup_tool()
    doc_tool = make_document_search_tool(store)

    def _registry_has(tool_name: str) -> bool:
        """True when ``mcp_registry`` currently advertises ``tool_name``."""
        if mcp_registry is None:
            return False
        try:
            return tool_name in mcp_registry.tools()
        except Exception:  # noqa: BLE001 - a broken registry must not crash routing
            return False

    # -- router node --------------------------------------------------------

    def router_node(state: AgentState) -> dict:
        """Pick a capability route: LLM-constrained choice, keyword fallback.

        We reuse the Module 11 router verbatim: ``route_question`` asks the LLM
        to name one tool and *falls back to ``keyword_route``* whenever the reply
        is not a clean tool name. That fallback is what makes routing work
        offline (the mock LLM never returns a valid tool name) and deterministic
        in tests. The chosen tool name is then mapped to a graph route.
        """
        question = state["question"]
        tools = [doc_tool, calculator_tool, order_tool]
        try:
            tool_name = route_question(question, llm, tools)
        except Exception:  # noqa: BLE001 - a router LLM failure degrades to keywords
            tool_name = keyword_route(question, tools)
        route = _ROUTE_FOR_TOOL.get(tool_name, ROUTE_GENERAL)
        return {
            "route": route,
            "trace": _trace("router", f"tool={tool_name} route={route}"),
        }

    def route_selector(state: AgentState) -> str:
        """Conditional-edge function: return the route label chosen upstream."""
        return state.get("route", ROUTE_GENERAL)

    # -- retrieval / grounded answer node ----------------------------------

    def retrieval_node(state: AgentState) -> dict:
        """Answer from the corpus via the RAG pipeline: cite sources or abstain.

        The pipeline already enforces the grounding contract (Module 08): it
        abstains when nothing relevant is retrieved and only credits sources
        that were actually in the supplied context. We surface a short evidence
        summary into state for the trace/dev view.

        ``loop_count`` is bumped every pass so the retry edge is bounded by
        ``max_loops`` — even though the single-shot pipeline normally answers in
        one pass, the cap makes any future retry provably finite (Module 10).
        """
        question = state["question"]
        loop_count = state.get("loop_count", 0) + 1

        retrieved = pipeline.retrieve(question)
        evidence = (
            ", ".join(f"{r.chunk.doc_id}:{r.score:.2f}" for r in retrieved)
            if retrieved
            else "(none)"
        )
        result = pipeline.answer(question)
        detail = (
            f"loop={loop_count} chunks={len(retrieved)} "
            f"abstained={result.abstained} sources={result.sources}"
        )
        return {
            "evidence": evidence,
            "answer": result.answer,
            "sources": result.sources,
            "loop_count": loop_count,
            "trace": _trace("retrieval", detail),
        }

    def retrieval_decision(state: AgentState) -> str:
        """Loop guard for the retrieval retry path.

        v1 answers in a single retrieval pass, so the normal decision is
        ``"done"``. The only way to ``"retry"`` is an empty answer *and* room
        under the cap; the cap is checked first, so retrieval can never loop past
        ``max_loops`` (the Module 10, Lab D pattern — kept here as the seam
        Module 17's iterative retrieval plugs into).
        """
        if state.get("loop_count", 0) >= max_loops:
            return "done"
        if not (state.get("answer") or "").strip():
            return "retry"
        return "done"

    # -- calculator node ----------------------------------------------------

    def calculator_node(state: AgentState) -> dict:
        """Compute the answer via MCP ``calculator.*`` if available, else local.

        Graceful fallback is a spec requirement: when no registry is connected
        (or the calculator server is down) we run the in-process ``calculator``
        tool instead, so a math question is always answered offline. The result
        is stored raw in ``tool_result``; the formatter renders it — and never
        attributes it to the documents.
        """
        question = state["question"]
        used = "local"
        if _registry_has(MCP_CALCULATOR_ADD):
            value = _try_mcp_calculator(mcp_registry, question)
            if value is not None:
                used = "mcp"
                return {
                    "tool_result": value,
                    "trace": _trace("calculator", f"backend=mcp result={value}"),
                }
            # MCP path could not parse a simple binary op — fall back to local.
        tool_result = calculator_tool.run({"expression": question})
        text = tool_result.output if tool_result.ok else (tool_result.error or "calculation failed")
        return {
            "tool_result": text,
            "trace": _trace("calculator", f"backend={used} ok={tool_result.ok}"),
        }

    # -- orders node --------------------------------------------------------

    def orders_node(state: AgentState) -> dict:
        """Look up an order via MCP ``orders.get_order_status`` (local fallback).

        Three outcomes, all handled without a crash (Module 13):
        - order found      -> the status record text;
        - order unknown    -> a safe "no such order" message;
        - system down / no id -> a clear "order system unavailable" answer.
        """
        question = state["question"]
        match = _ORDER_ID_RE.search(question)
        if not match:
            return {
                "tool_result": (
                    "I could not find an order id in your question. Order ids look "
                    "like TC-1234 — please include one."
                ),
                "trace": _trace("orders", "backend=none reason=no_order_id"),
            }
        order_id = match.group(0).upper()

        if _registry_has(MCP_ORDERS_STATUS):
            ok, text = _try_mcp_order(mcp_registry, order_id)
            backend = "mcp"
        else:
            result = order_tool.run({"order_id": order_id})
            ok = result.ok
            text = result.output if result.ok else (result.error or "order lookup failed")
            backend = "local"
        return {
            "tool_result": text,
            "trace": _trace("orders", f"backend={backend} order={order_id} ok={ok}"),
        }

    # -- general LLM node ---------------------------------------------------

    def general_node(state: AgentState) -> dict:
        """Answer an open / conversational request with a plain LLM call.

        No tool, no retrieval — greetings, thanks, "explain in your own words".
        The formatter passes this straight through (no sources), so the agent
        never pretends a chit-chat reply was grounded in company documents.
        """
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
            ChatMessage(role="user", content=question),
        ]
        try:
            reply = llm.complete(messages, temperature=0.0).content
        except Exception as exc:  # noqa: BLE001 - an LLM failure is data, not a crash
            reply = f"I'm unable to answer that right now ({exc})."
        return {
            "tool_result": reply,
            "trace": _trace("general", f"chars={len(reply)}"),
        }

    # -- response formatter node -------------------------------------------

    def formatter_node(state: AgentState) -> dict:
        """Produce the final, consistent answer shape for whichever route ran.

        The retrieval node has already written ``answer``/``sources``; the tool
        and general nodes wrote ``tool_result`` and no sources. The formatter's
        job is to (a) give every route the same output contract and (b) keep the
        provenance honest — only the retrieval route may carry sources, so a
        calculator or order result is never dressed up as a document answer.
        """
        route = state.get("route", ROUTE_GENERAL)

        if route == ROUTE_RETRIEVAL:
            answer = state.get("answer", "") or ABSTENTION_TEXT
            sources = state.get("sources", [])
            return {
                "answer": answer,
                "sources": sources,
                "trace": _trace("formatter", f"route=retrieval sources={sources}"),
            }

        # Non-document routes: the answer is the tool/general text, no sources.
        answer = state.get("tool_result", "") or "I don't have a result for that."
        if route == ROUTE_CALCULATOR:
            answer = f"The result is {answer}."
        return {
            "answer": answer,
            "sources": [],
            "trace": _trace("formatter", f"route={route} sources=[]"),
        }

    # -- wiring -------------------------------------------------------------

    graph = StateGraph(AgentState)
    graph.add_node("router", router_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("calculator", calculator_node)
    graph.add_node("orders", orders_node)
    graph.add_node("general", general_node)
    graph.add_node("formatter", formatter_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        route_selector,
        {
            ROUTE_RETRIEVAL: "retrieval",
            ROUTE_CALCULATOR: "calculator",
            ROUTE_ORDERS: "orders",
            ROUTE_GENERAL: "general",
        },
    )
    # Retrieval has a bounded self-retry seam; the other routes go straight on.
    graph.add_conditional_edges(
        "retrieval",
        retrieval_decision,
        {"retry": "retrieval", "done": "formatter"},
    )
    graph.add_edge("calculator", "formatter")
    graph.add_edge("orders", "formatter")
    graph.add_edge("general", "formatter")
    graph.add_edge("formatter", END)
    return graph.compile()


# -- MCP call bridges (kept out of the nodes so the nodes stay readable) -----


def _try_mcp_calculator(registry: Any, question: str) -> str | None:
    """Compute ``question`` via the calculator MCP server, or ``None``.

    The MCP calculator exposes binary ops (add/subtract/multiply/divide), not a
    free-form expression evaluator, so we only use it for a simple two-operand
    form and otherwise return ``None`` to let the caller fall back to the local
    tool (which handles percentages and multi-step expressions).
    """
    match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*([-+*/x])\s*(-?\d+(?:\.\d+)?)",
        question.replace(",", ""),
        re.IGNORECASE,
    )
    if not match:
        return None
    a = float(match.group(1))
    op = match.group(2).lower()
    b = float(match.group(3))
    tool = {"+": "add", "-": "subtract", "*": "multiply", "x": "multiply", "/": "divide"}[op]
    try:
        result = registry.call(f"calculator.{tool}", {"a": a, "b": b})
    except Exception:  # noqa: BLE001 - degrade to the local tool on any MCP error
        return None
    if result.is_error:
        return None
    if result.structured_content and "result" in result.structured_content:
        value = result.structured_content["result"]
        return str(int(value)) if float(value).is_integer() else str(value)
    return result.content[0].text if result.content else None


def _try_mcp_order(registry: Any, order_id: str) -> tuple[bool, str]:
    """Look up ``order_id`` via the orders MCP server.

    Returns ``(ok, text)``. A down server or an unknown order both come back as
    ``ok=False`` with a clear message — never a raised exception.
    """
    try:
        result = registry.call(MCP_ORDERS_STATUS, {"order_id": order_id})
    except Exception as exc:  # noqa: BLE001 - a broken session degrades cleanly
        return False, f"The order system is unavailable right now ({exc})."
    text = result.content[0].text if result.content else ""
    if result.is_error:
        # The server returns is_error for an unknown id *and* for being down;
        # either way the message is safe to relay to the user.
        return False, text or f"No status available for order {order_id}."
    if result.structured_content:
        sc = result.structured_content
        parts = [f"Order {sc.get('order_id', order_id)}: status {sc.get('status', 'unknown')}"]
        if sc.get("last_update"):
            parts.append(f"last update: {sc['last_update']}")
        if sc.get("estimated_delivery"):
            parts.append(f"estimated delivery: {sc['estimated_delivery']}")
        return True, "\n".join(parts)
    return True, text
