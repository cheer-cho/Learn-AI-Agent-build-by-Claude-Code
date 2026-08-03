"""Module 10 starter — build four LangGraph graphs for TechCorp.

Work through lab.md and replace each TODO. Lab A is fully implemented for you
as the pattern to copy: a state TypedDict, node functions that return PARTIAL
updates, and graph wiring with add_edge / START / END. Labs B, C, and D leave
the state, nodes, and wiring for you.

Run your work (offline, no API key needed):
    uv run python course/10_langgraph/starter/graphs.py
Check it:
    uv run pytest course/10_langgraph -q
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from techcorp_agent.llm.base import LLMClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage

# ---------------------------------------------------------------------------
# Observability helper (given — do not change)
# ---------------------------------------------------------------------------
# `trace` carries a `list[str]` with an `operator.add` reducer, so returning
# {"trace": [...]} from a node APPENDS instead of overwriting. That is how the
# run records the path it took. This is the seed of Module 19's tracing.


def trace(node: str, detail: str = "") -> list[str]:
    """One structured trace line, returned as a single-item list for the reducer."""
    line = f"[node={node}]"
    if detail:
        line += f" {detail}"
    return [line]


def print_trace(title: str, final_state: dict) -> None:
    print(f"\n=== {title} ===")
    for line in final_state.get("trace", []):
        print(f"  {line}")
    print(f"  final status: {final_state.get('status', 'done')}")


# ===========================================================================
# Lab A — Basic graph: Greeting -> Enhancement -> END   (FULLY IMPLEMENTED)
# Copy this shape for the other labs.
# ===========================================================================


class GreetingState(TypedDict):
    name: str
    message: str
    status: str
    trace: Annotated[list[str], operator.add]


def greeting_node(state: GreetingState) -> dict:
    """A node returns only the keys it changed — a partial update."""
    message = f"Hello, {state['name']}!"
    return {"message": message, "trace": trace("greeting", f"message={message!r}")}


def enhancement_node(state: GreetingState) -> dict:
    message = f"{state['message']} Welcome to TechCorp."
    return {
        "message": message,
        "status": "complete",
        "trace": trace("enhancement", f"message={message!r}"),
    }


def build_lab_a() -> object:
    graph = StateGraph(GreetingState)
    graph.add_node("greeting", greeting_node)
    graph.add_node("enhancement", enhancement_node)
    graph.add_edge(START, "greeting")
    graph.add_edge("greeting", "enhancement")
    graph.add_edge("enhancement", END)
    return graph.compile()


def main_lab_a() -> dict:
    app = build_lab_a()
    final = app.invoke({"name": "Dana", "message": "", "status": "pending", "trace": []})
    print_trace("Lab A — Basic graph", final)
    print(f"  message: {final['message']}")
    return final


# ===========================================================================
# Lab B — Draft and review: Outline -> Draft -> Review -> Finalize
# Each node makes ONE LLM call via the injected client.
# ===========================================================================


class DraftState(TypedDict):
    topic: str
    outline: str
    draft: str
    review: str
    final: str
    status: str
    trace: Annotated[list[str], operator.add]


def _ask(client: LLMClient, system: str, user: str) -> str:
    """One deterministic LLM call, content only (given helper)."""
    messages = [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=user),
    ]
    return client.complete(messages, temperature=0.0).content


def make_draft_graph(client: LLMClient) -> object:
    """Build Lab B. The client is injected so tests can script exact replies."""

    def outline_node(state: DraftState) -> dict:
        outline = _ask(
            client,
            "You are a TechCorp technical writer. Produce a short outline.",
            f"Outline a document about: {state['topic']}",
        )
        return {"outline": outline, "trace": trace("outline", f"chars={len(outline)}")}

    # TODO (Lab B): implement draft_node.
    #   - call _ask(client, <editor/writer system prompt>, "Write a draft from
    #     this outline:\n" + state["outline"])
    #   - return {"draft": <result>, "trace": trace("draft", f"chars={len(<result>)}")}

    # TODO (Lab B): implement review_node.
    #   - _ask over state["draft"], return {"review": ..., "trace": trace("review", ...)}

    # TODO (Lab B): implement finalize_node.
    #   - _ask over state["draft"] + state["review"]
    #   - return {"final": ..., "status": "finalized", "trace": trace("finalize", ...)}

    graph = StateGraph(DraftState)
    graph.add_node("outline", outline_node)
    # TODO (Lab B): add_node for draft, review, finalize.
    graph.add_edge(START, "outline")
    # TODO (Lab B): add edges outline->draft->review->finalize->END.
    return graph.compile()


def _scripted_draft_client() -> MockLLMClient:
    """Fixed replies so offline output is exact (given)."""
    return MockLLMClient(
        responses=[
            "1. What GDPR is\n2. Key rights\n3. TechCorp obligations",
            "GDPR is an EU regulation. Users have rights. TechCorp must comply.",
            "Add a concrete example for each right; tighten the intro.",
            "GDPR is an EU data-protection regulation granting users rights such "
            "as access and erasure; TechCorp complies by honoring those requests.",
        ]
    )


def main_lab_b(client: LLMClient | None = None) -> dict:
    client = client or _scripted_draft_client()
    app = make_draft_graph(client)
    final = app.invoke(
        {
            "topic": "GDPR for TechCorp staff",
            "outline": "",
            "draft": "",
            "review": "",
            "final": "",
            "status": "pending",
            "trace": [],
        }
    )
    print_trace("Lab B — Draft and review", final)
    print(f"  final text: {final.get('final', '')}")
    return final


# ===========================================================================
# Lab C — Conditional route:
#   classify -> (short_explanation | detailed_policy_analysis) -> END
# ===========================================================================


class RouteState(TypedDict):
    request: str
    complexity: str
    route: str
    answer: str
    status: str
    trace: Annotated[list[str], operator.add]


_COMPLEX_MARKERS = ("analyze", "analysis", "gdpr", "policy", "compliance", "detailed")


def classify_node(state: RouteState) -> dict:
    """Set complexity to 'simple' or 'complex' from the request text (given)."""
    text = state["request"].lower()
    complexity = "complex" if any(m in text for m in _COMPLEX_MARKERS) else "simple"
    return {"complexity": complexity, "trace": trace("classify", f"complexity={complexity}")}


def route_request(state: RouteState) -> str:
    """Return a routing LABEL, mapped to a node by the conditional edge."""
    # TODO (Lab C): return "detailed" when complexity is "complex", else "short".
    raise NotImplementedError("route_request — see lab.md Lab C")


def short_explanation_node(state: RouteState) -> dict:
    answer = f"Short answer: {state['request']} — see the TechCorp handbook for details."
    return {
        "answer": answer,
        "route": "short",
        "status": "answered",
        "trace": trace("short_explanation", "route=short"),
    }


def detailed_policy_analysis_node(state: RouteState) -> dict:
    answer = (
        f"Detailed policy analysis for: {state['request']}. "
        "Requirements, gaps, and recommendations follow TechCorp's GDPR review process."
    )
    return {
        "answer": answer,
        "route": "detailed",
        "status": "answered",
        "trace": trace("detailed_policy_analysis", "route=detailed"),
    }


def build_lab_c() -> object:
    graph = StateGraph(RouteState)
    graph.add_node("classify", classify_node)
    graph.add_node("short_explanation", short_explanation_node)
    graph.add_node("detailed_policy_analysis", detailed_policy_analysis_node)
    graph.add_edge(START, "classify")
    # TODO (Lab C): add a conditional edge from "classify" using route_request
    #   with the path map {"short": "short_explanation",
    #                      "detailed": "detailed_policy_analysis"}.
    # TODO (Lab C): add edges from both branch nodes to END.
    raise NotImplementedError("build_lab_c wiring — see lab.md Lab C")


def run_lab_c(request: str) -> dict:
    app = build_lab_c()
    return app.invoke(
        {
            "request": request,
            "complexity": "",
            "route": "",
            "answer": "",
            "status": "pending",
            "trace": [],
        }
    )


def main_lab_c() -> tuple[dict, dict]:
    simple = run_lab_c("What are TechCorp office hours?")
    print_trace("Lab C — Conditional route (simple request)", simple)
    print(f"  route: {simple['route']}  answer: {simple['answer']}")

    complex_ = run_lab_c("Analyze our GDPR data-retention policy for compliance gaps.")
    print_trace("Lab C — Conditional route (complex request)", complex_)
    print(f"  route: {complex_['route']}  answer: {complex_['answer']}")
    return simple, complex_


# ===========================================================================
# Lab D — Iterative retrieval with a STRICT max-iteration cap:
#   analyze_evidence -> (retrieve_more -> analyze_evidence)* -> finalize -> END
# ===========================================================================

MAX_ITERATIONS = 3
EVIDENCE_THRESHOLD = 0.75


class RetrievalState(TypedDict):
    question: str
    scores: list[float]
    evidence_score: float
    iteration: int
    max_iterations: int
    threshold: float
    status: str
    trace: Annotated[list[str], operator.add]


def analyze_evidence_node(state: RetrievalState) -> dict:
    """Score the current evidence and increment the iteration counter (given)."""
    iteration = state["iteration"] + 1
    scores = state["scores"]
    idx = min(iteration - 1, len(scores) - 1) if scores else 0
    score = scores[idx] if scores else 0.0
    return {
        "iteration": iteration,
        "evidence_score": score,
        "trace": trace("analyze_evidence", f"iteration={iteration} score={score:.2f}"),
    }


def retrieve_more_node(state: RetrievalState) -> dict:
    return {"trace": trace("retrieve_more", f"after iteration={state['iteration']}")}


def evidence_decision(state: RetrievalState) -> str:
    """Return 'stop' or 'retry'. The cap must be checked so the loop is finite."""
    # TODO (Lab D): return "stop" when evidence_score >= threshold.
    # TODO (Lab D): ALSO return "stop" when iteration >= max_iterations
    #   (this is the guard that prevents an infinite loop).
    # TODO (Lab D): otherwise return "retry".
    raise NotImplementedError("evidence_decision — see lab.md Lab D")


def finalize_retrieval_node(state: RetrievalState) -> dict:
    passed = state["evidence_score"] >= state["threshold"]
    status = "sufficient_evidence" if passed else "max_iterations_reached"
    return {"status": status, "trace": trace("finalize", f"status={status}")}


def build_lab_d() -> object:
    graph = StateGraph(RetrievalState)
    graph.add_node("analyze_evidence", analyze_evidence_node)
    graph.add_node("retrieve_more", retrieve_more_node)
    graph.add_node("finalize", finalize_retrieval_node)
    graph.add_edge(START, "analyze_evidence")
    # TODO (Lab D): conditional edge from "analyze_evidence" using evidence_decision
    #   with path map {"retry": "retrieve_more", "stop": "finalize"}.
    # TODO (Lab D): add the LOOP edge "retrieve_more" -> "analyze_evidence".
    # TODO (Lab D): add edge "finalize" -> END.
    raise NotImplementedError("build_lab_d wiring — see lab.md Lab D")


def run_lab_d(scores: list[float]) -> dict:
    app = build_lab_d()
    return app.invoke(
        {
            "question": "Does TechCorp's policy meet GDPR erasure requirements?",
            "scores": scores,
            "evidence_score": 0.0,
            "iteration": 0,
            "max_iterations": MAX_ITERATIONS,
            "threshold": EVIDENCE_THRESHOLD,
            "status": "pending",
            "trace": [],
        }
    )


def main_lab_d() -> tuple[dict, dict]:
    capped = run_lab_d([0.20, 0.30, 0.40, 0.40])
    print_trace("Lab D — Iterative retrieval (evidence never improves)", capped)
    print(f"  iterations: {capped['iteration']} (cap={MAX_ITERATIONS})")

    early = run_lab_d([0.40, 0.90])
    print_trace("Lab D — Iterative retrieval (evidence passes)", early)
    print(f"  iterations: {early['iteration']} (stopped early)")
    return capped, early


def main() -> int:
    main_lab_a()
    main_lab_b()
    main_lab_c()
    main_lab_d()
    print("\nAll four labs ran offline with deterministic mocks.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NotImplementedError as exc:
        print(f"\nNot implemented yet: {exc}")
        print("Open course/10_langgraph/lab.md and work through the labs in order.")
        raise SystemExit(1) from None
