"""Module 14 lab — assemble the TechCorp Knowledge Agent v1 yourself.

Everything you need is already built and imported below — the RAG pipeline
(Module 08), the tools and the router with its keyword fallback (Module 11),
the MCP bridge (Modules 12-13), and the LangGraph patterns (Module 10). Your
job is the CAPSTONE job: wire them into one graph. The TODOs sit at the
interesting joints:

    1. the router node        — LLM choice with the deterministic fallback,
                                then tool name -> graph route;
    2. the conditional edges  — route label -> node, exactly four ways;
    3. the calculator fallback — MCP when available, local tool otherwise;
    4. the formatter rules    — one output shape, sources ONLY for retrieval.

When every TODO is gone, run it offline:

    TECHCORP_OFFLINE=true uv run python course/14_capstone_v1/starter/capstone.py

and the tests stop skipping:

    uv run pytest course/14_capstone_v1 -q

Compare your finished assembly with `techcorp_agent.capstone.graph.build_graph`
— they should be the same wiring. That is the point: the library graph is not
magic, it is exactly what you just built.
"""

from __future__ import annotations

import re

from langgraph.graph import END, START, StateGraph

from techcorp_agent.capstone import build_offline_store
from techcorp_agent.capstone.state import AgentState
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT, RAGPipeline
from techcorp_agent.schemas import ChatMessage
from techcorp_agent.tools.calculator import make_calculator_tool
from techcorp_agent.tools.orders import make_order_lookup_tool
from techcorp_agent.tools.router import keyword_route, route_question
from techcorp_agent.tools.search_docs import make_document_search_tool
from techcorp_agent.vectorstore.chroma_store import VectorStore

# The four capability routes your router must choose between.
ROUTE_RETRIEVAL = "retrieval"
ROUTE_CALCULATOR = "calculator"
ROUTE_ORDERS = "orders"
ROUTE_GENERAL = "general"

_ORDER_ID_RE = re.compile(r"\bTC-\d{3,}\b", re.IGNORECASE)


def _trace(node: str, detail: str = "") -> list[str]:
    """One structured trace line (single-item list for the operator.add reducer)."""
    line = f"[node={node}]"
    if detail:
        line += f" {detail}"
    return [line]


def build_agent(
    llm: LLMClient,
    store: VectorStore,
    mcp_registry=None,
    max_loops: int = 3,
):
    """Assemble and compile the capstone graph from the pre-built components."""
    pipeline = RAGPipeline(store, llm)
    calculator_tool = make_calculator_tool()
    order_tool = make_order_lookup_tool()
    doc_tool = make_document_search_tool(store)

    def _registry_has(tool_name: str) -> bool:
        """True when the MCP registry is connected and advertises `tool_name`."""
        if mcp_registry is None:
            return False
        try:
            return tool_name in mcp_registry.tools()
        except Exception:
            return False

    # -- 1) the router node --------------------------------------------------

    def router_node(state: AgentState) -> dict:
        question = state["question"]
        tools = [doc_tool, calculator_tool, order_tool]

        # TODO: Pick a tool name for `question`.
        #   - Call route_question(question, llm, tools) — it asks the LLM to name
        #     ONE tool and already falls back to keyword_route on any bad reply.
        #   - Wrap the call in try/except and fall back to
        #     keyword_route(question, tools) if the LLM call itself raises.
        tool_name = "none"

        # TODO: Map the tool name to a graph route:
        #   "document_search" -> ROUTE_RETRIEVAL, "calculator" -> ROUTE_CALCULATOR,
        #   "order_lookup" -> ROUTE_ORDERS, anything else -> ROUTE_GENERAL.
        route = ROUTE_GENERAL

        return {
            "route": route,
            "trace": _trace("router", f"tool={tool_name} route={route}"),
        }

    def route_selector(state: AgentState) -> str:
        """Conditional-edge function: return the route chosen by the router."""
        return state.get("route", ROUTE_GENERAL)

    # -- retrieval / grounded answer node (pre-built for you) ----------------

    def retrieval_node(state: AgentState) -> dict:
        """Answer from the corpus via the reused RAGPipeline: cite or abstain."""
        question = state["question"]
        loop_count = state.get("loop_count", 0) + 1
        retrieved = pipeline.retrieve(question)
        evidence = (
            ", ".join(f"{r.chunk.doc_id}:{r.score:.2f}" for r in retrieved)
            if retrieved
            else "(none)"
        )
        result = pipeline.answer(question)
        return {
            "evidence": evidence,
            "answer": result.answer,
            "sources": result.sources,
            "loop_count": loop_count,
            "trace": _trace(
                "retrieval",
                f"loop={loop_count} chunks={len(retrieved)} "
                f"abstained={result.abstained} sources={result.sources}",
            ),
        }

    def retrieval_decision(state: AgentState) -> str:
        """Bounded retry seam: cap FIRST, so the loop is provably finite."""
        if state.get("loop_count", 0) >= max_loops:
            return "done"
        if not (state.get("answer") or "").strip():
            return "retry"
        return "done"

    # -- 3) the calculator node (finish the fallback) -------------------------

    def calculator_node(state: AgentState) -> dict:
        question = state["question"]

        # TODO: Graceful fallback — the spec requires a math question to be
        # answered whether or not MCP is up:
        #   1. If _registry_has("calculator.add"), try the MCP path first:
        #      parse a simple "A <op> B" from the question, call
        #      mcp_registry.call(f"calculator.{tool}", {"a": a, "b": b}) and use
        #      result.structured_content["result"] when not result.is_error.
        #      (See techcorp_agent.capstone.graph._try_mcp_calculator.)
        #   2. Otherwise (or if the MCP path can't handle it), run the LOCAL
        #      tool: calculator_tool.run({"expression": question}) and use
        #      .output on success or .error on failure.
        # Store the resulting text in `text` and the backend name in `backend`.
        backend = "local"
        text = "TODO"

        return {
            "tool_result": text,
            "trace": _trace("calculator", f"backend={backend}"),
        }

    # -- orders node (pre-built for you) --------------------------------------

    def orders_node(state: AgentState) -> dict:
        """Order lookup: MCP when available, local tool otherwise, never a crash."""
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
        if _registry_has("orders.get_order_status"):
            try:
                result = mcp_registry.call("orders.get_order_status", {"order_id": order_id})
                ok = not result.is_error
                text = result.content[0].text if result.content else ""
                backend = "mcp"
            except Exception as exc:
                ok, text, backend = False, f"The order system is unavailable ({exc}).", "mcp"
        else:
            result = order_tool.run({"order_id": order_id})
            ok = result.ok
            text = result.output if result.ok else (result.error or "order lookup failed")
            backend = "local"
        return {
            "tool_result": text,
            "trace": _trace("orders", f"backend={backend} order={order_id} ok={ok}"),
        }

    # -- general LLM node (pre-built for you) ---------------------------------

    def general_node(state: AgentState) -> dict:
        """Plain LLM reply for greetings / open questions — no tools, no sources."""
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are TechCorp's internal assistant. Answer the user's "
                    "general request briefly and helpfully. This is not a "
                    "company-policy question, so do not cite documents."
                ),
            ),
            ChatMessage(role="user", content=state["question"]),
        ]
        try:
            reply = llm.complete(messages, temperature=0.0).content
        except Exception as exc:
            reply = f"I'm unable to answer that right now ({exc})."
        return {"tool_result": reply, "trace": _trace("general", f"chars={len(reply)}")}

    # -- 4) the response formatter (finish the rules) --------------------------

    def formatter_node(state: AgentState) -> dict:
        route = state.get("route", ROUTE_GENERAL)

        # TODO: Enforce ONE consistent output shape with HONEST provenance:
        #   - retrieval route: answer = state["answer"] (or ABSTENTION_TEXT if
        #     empty), sources = state["sources"] — the ONLY route that may
        #     carry sources;
        #   - calculator route: answer = f"The result is {state['tool_result']}."
        #     and sources = [] — NEVER attribute a computed number to documents;
        #   - orders / general: answer = state["tool_result"], sources = [].
        # Always return an "answer" string, a "sources" list, and a trace line.
        answer = "TODO"
        sources: list[str] = []

        return {
            "answer": answer,
            "sources": sources,
            "trace": _trace("formatter", f"route={route} sources={sources}"),
        }

    # -- 2) the wiring ---------------------------------------------------------

    graph = StateGraph(AgentState)
    graph.add_node("router", router_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("calculator", calculator_node)
    graph.add_node("orders", orders_node)
    graph.add_node("general", general_node)
    graph.add_node("formatter", formatter_node)

    graph.add_edge(START, "router")

    # TODO: Add the conditional edges out of the router:
    #   graph.add_conditional_edges("router", route_selector, {<route>: <node>, ...})
    #   — all four routes, each to its node.

    # TODO: Wire the rest:
    #   - retrieval has a BOUNDED retry seam:
    #     graph.add_conditional_edges("retrieval", retrieval_decision,
    #                                 {"retry": "retrieval", "done": "formatter"})
    #   - calculator, orders, and general each go straight to "formatter";
    #   - formatter goes to END.

    return graph.compile()


def ask(app, question: str, conversation_id: str = "demo") -> dict:
    """Run one question through the compiled graph and return the final state."""
    return app.invoke(
        {
            "conversation_id": conversation_id,
            "question": question,
            "trace": [],
            "loop_count": 0,
        }
    )


def main() -> int:
    """Walk the five required sample interactions offline (see lab.md)."""
    store = build_offline_store()

    demos = [
        # (title, question, scripted LLM responses or None for the echo mock)
        (
            "1) Policy question",
            "Can an international employee work remotely from another country?",
            [
                "document_search",
                "Yes - employees may work remotely from another country for up to 30 "
                "calendar days per year, with manager approval recorded before travel "
                "and 60 days advance notice; stays longer than 30 days additionally "
                "require joint Legal and HR approval.\nSOURCES: hr-international-remote",
            ],
        ),
        (
            "2) Semantic wording difference",
            "Am I allowed to wear denim at headquarters?",
            [
                "document_search",
                "Yes - jeans (denim) are allowed at headquarters as long as they are "
                "clean and free of rips, but not during client meetings.\n"
                "SOURCES: hr-dress-code",
            ],
        ),
        ("3) Calculator", "What is 17.5% of 8,400?", None),
        ("4a) Order lookup (known)", "What is happening with order TC-1234?", None),
        ("4b) Order lookup (unknown)", "What is happening with order TC-9999?", None),
        (
            "5) Unanswerable",
            "What is TechCorp's policy for working from the Moon?",
            ["document_search", f"{ABSTENTION_TEXT}\nSOURCES: none"],
        ),
    ]
    for title, question, responses in demos:
        llm = MockLLMClient(responses=responses) if responses else MockLLMClient()
        app = build_agent(llm, store)
        state = ask(app, question)
        print(f"--- {title} ---")
        print(f"Q: {question}")
        print(f"A: {state.get('answer')}")
        if state.get("sources"):
            print(f"Sources: {', '.join(state['sources'])}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
