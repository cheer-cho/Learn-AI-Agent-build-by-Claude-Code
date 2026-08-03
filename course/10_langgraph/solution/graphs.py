"""Module 10 solution — LangGraph fundamentals for TechCorp.

Four graphs, each a `build_lab_X()` that returns a compiled graph plus a
`main_lab_X()` that runs it offline and prints the observability trace.

Run all four offline (no API key required):

    uv run python course/10_langgraph/solution/graphs.py

Everything uses deterministic mocks (scripted MockLLMClient for the LLM labs),
so the printed output — and the tests — are exact.

Verified against langgraph 1.2.10:
- StateGraph(TypedDict) with add_node / add_edge / add_conditional_edges
- START / END sentinels from langgraph.graph
- compile() -> .invoke(state) returns the final merged state
- Annotated[list, operator.add] reducer to append to a shared trace log
- conditional edges with an explicit path_map {label: node}
- a self-capped loop (max-iteration guard) so it can never run forever
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from techcorp_agent.llm.base import LLMClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage

# ---------------------------------------------------------------------------
# Observability helper
# ---------------------------------------------------------------------------
# Every graph carries a `trace: list[str]` field with an `operator.add` reducer.
# When two nodes each return {"trace": [...]}, LangGraph *appends* the lists
# instead of overwriting — that is a "reducer". `trace(...)` builds one uniform
# line so tests can assert on the exact sequence and learners can read the run.
# This tiny pattern foreshadows the real tracing you build in Module 19.


def trace(node: str, detail: str = "") -> list[str]:
    """One structured trace line, returned as a single-item list for the reducer."""
    line = f"[node={node}]"
    if detail:
        line += f" {detail}"
    return [line]


def print_trace(title: str, final_state: dict) -> None:
    """Render the recorded trace and the final status for a completed run."""
    print(f"\n=== {title} ===")
    for line in final_state.get("trace", []):
        print(f"  {line}")
    print(f"  final status: {final_state.get('status', 'done')}")


# ===========================================================================
# Lab A — Basic graph:  Greeting -> Enhancement -> END
# ===========================================================================


class GreetingState(TypedDict):
    """Shared state for Lab A. `trace` accumulates; the rest are overwritten."""

    name: str
    message: str
    status: str
    trace: Annotated[list[str], operator.add]


def greeting_node(state: GreetingState) -> dict:
    """Entry node: produce a greeting from the name in state.

    A node returns a PARTIAL update — only the keys it changed. LangGraph
    merges that dict into the shared state; it never has to return the whole
    thing.
    """
    message = f"Hello, {state['name']}!"
    return {"message": message, "trace": trace("greeting", f"message={message!r}")}


def enhancement_node(state: GreetingState) -> dict:
    """Second node: enrich the greeting produced upstream."""
    message = f"{state['message']} Welcome to TechCorp."
    return {
        "message": message,
        "status": "complete",
        "trace": trace("enhancement", f"message={message!r}"),
    }


def build_lab_a() -> object:
    """Wire Greeting -> Enhancement -> END and compile."""
    graph = StateGraph(GreetingState)
    graph.add_node("greeting", greeting_node)
    graph.add_node("enhancement", enhancement_node)
    graph.add_edge(START, "greeting")  # entry point
    graph.add_edge("greeting", "enhancement")
    graph.add_edge("enhancement", END)  # end state
    return graph.compile()


def main_lab_a() -> dict:
    app = build_lab_a()
    final = app.invoke({"name": "Dana", "message": "", "status": "pending", "trace": []})
    print_trace("Lab A — Basic graph", final)
    print(f"  message: {final['message']}")
    return final


# ===========================================================================
# Lab B — Draft and review:  Outline -> Draft -> Review -> Finalize
# Each node is one LLM call via the injected client.
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
    """One deterministic (temperature=0) LLM call, content only."""
    messages = [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=user),
    ]
    return client.complete(messages, temperature=0.0).content


def make_draft_graph(client: LLMClient) -> object:
    """Build Lab B with `client` captured by each node (dependency injection).

    Passing the client in — rather than constructing it inside the nodes — is
    what lets tests inject a scripted MockLLMClient and get exact output.
    """

    def outline_node(state: DraftState) -> dict:
        outline = _ask(
            client,
            "You are a TechCorp technical writer. Produce a short outline.",
            f"Outline a document about: {state['topic']}",
        )
        return {"outline": outline, "trace": trace("outline", f"chars={len(outline)}")}

    def draft_node(state: DraftState) -> dict:
        draft = _ask(
            client,
            "You are a TechCorp technical writer. Expand an outline into a draft.",
            f"Write a draft from this outline:\n{state['outline']}",
        )
        return {"draft": draft, "trace": trace("draft", f"chars={len(draft)}")}

    def review_node(state: DraftState) -> dict:
        review = _ask(
            client,
            "You are a TechCorp editor. Give terse review notes.",
            f"Review this draft:\n{state['draft']}",
        )
        return {"review": review, "trace": trace("review", f"chars={len(review)}")}

    def finalize_node(state: DraftState) -> dict:
        final = _ask(
            client,
            "You are a TechCorp technical writer. Apply review notes and finalize.",
            f"Draft:\n{state['draft']}\n\nReview notes:\n{state['review']}\n\nProduce the final text.",
        )
        return {
            "final": final,
            "status": "finalized",
            "trace": trace("finalize", f"chars={len(final)}"),
        }

    graph = StateGraph(DraftState)
    graph.add_node("outline", outline_node)
    graph.add_node("draft", draft_node)
    graph.add_node("review", review_node)
    graph.add_node("finalize", finalize_node)
    graph.add_edge(START, "outline")
    graph.add_edge("outline", "draft")
    graph.add_edge("draft", "review")
    graph.add_edge("review", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def _scripted_draft_client() -> MockLLMClient:
    """Fixed replies so Lab B's offline output is exact and testable."""
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
    print(f"  final text: {final['final']}")
    return final


# ===========================================================================
# Lab C — Conditional route:
#   classify -> (short_explanation | detailed_policy_analysis) -> END
# ===========================================================================


class RouteState(TypedDict):
    request: str
    complexity: str  # "simple" or "complex" — set by the classifier
    route: str  # which branch was actually taken (recorded for observability)
    answer: str
    status: str
    trace: Annotated[list[str], operator.add]


# Words that mark a request as needing the detailed policy branch.
_COMPLEX_MARKERS = ("analyze", "analysis", "gdpr", "policy", "compliance", "detailed")


def classify_node(state: RouteState) -> dict:
    """Decide whether the request is simple or complex (no LLM needed offline)."""
    text = state["request"].lower()
    complexity = "complex" if any(m in text for m in _COMPLEX_MARKERS) else "simple"
    return {"complexity": complexity, "trace": trace("classify", f"complexity={complexity}")}


def route_request(state: RouteState) -> str:
    """The routing function for the conditional edge.

    It returns a *label*; the path_map on the edge maps that label to a node.
    Returning a label (not a node name) keeps routing decisions readable and
    lets the wiring decide where each label goes.
    """
    return "detailed" if state["complexity"] == "complex" else "short"


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
    # Conditional edge: run route_request, then follow its label via the map.
    graph.add_conditional_edges(
        "classify",
        route_request,
        {"short": "short_explanation", "detailed": "detailed_policy_analysis"},
    )
    graph.add_edge("short_explanation", END)
    graph.add_edge("detailed_policy_analysis", END)
    return graph.compile()


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
#   analyze_evidence -> (retrieve_more -> analyze_evidence)* -> END
#
# The loop stops when EITHER the evidence score clears the threshold OR the
# iteration count hits the cap. The cap makes the loop provably finite — it
# can never run forever, even if the evidence never improves.
# ===========================================================================

MAX_ITERATIONS = 3
EVIDENCE_THRESHOLD = 0.75


class RetrievalState(TypedDict):
    question: str
    # `scores` is a scripted list of evidence scores, consumed one per analysis
    # pass. In a real graph this would be a similarity score from the vector
    # store (Module 07); here it is deterministic so tests are exact.
    scores: list[float]
    evidence_score: float
    iteration: int
    max_iterations: int
    threshold: float
    status: str
    trace: Annotated[list[str], operator.add]


def analyze_evidence_node(state: RetrievalState) -> dict:
    """Score the current evidence and bump the iteration counter."""
    iteration = state["iteration"] + 1
    scores = state["scores"]
    # Use the next scripted score, or repeat the last one once exhausted.
    idx = min(iteration - 1, len(scores) - 1) if scores else 0
    score = scores[idx] if scores else 0.0
    return {
        "iteration": iteration,
        "evidence_score": score,
        "trace": trace(
            "analyze_evidence",
            f"iteration={iteration} score={score:.2f}",
        ),
    }


def retrieve_more_node(state: RetrievalState) -> dict:
    """Loop body: fetch more evidence before analyzing again."""
    return {"trace": trace("retrieve_more", f"after iteration={state['iteration']}")}


def evidence_decision(state: RetrievalState) -> str:
    """Return 'stop' or 'retry' — the loop guard.

    Two independent stop conditions, and the cap is checked FIRST so a stuck
    retrieval (score never improving) can never loop past `max_iterations`.
    """
    if state["evidence_score"] >= state["threshold"]:
        return "stop"
    if state["iteration"] >= state["max_iterations"]:
        return "stop"
    return "retry"


def finalize_retrieval_node(state: RetrievalState) -> dict:
    """Set the terminal status based on whether the threshold was met."""
    passed = state["evidence_score"] >= state["threshold"]
    status = "sufficient_evidence" if passed else "max_iterations_reached"
    return {"status": status, "trace": trace("finalize", f"status={status}")}


def build_lab_d() -> object:
    graph = StateGraph(RetrievalState)
    graph.add_node("analyze_evidence", analyze_evidence_node)
    graph.add_node("retrieve_more", retrieve_more_node)
    graph.add_node("finalize", finalize_retrieval_node)
    graph.add_edge(START, "analyze_evidence")
    # After analysis: either loop back through retrieve_more, or finalize.
    graph.add_conditional_edges(
        "analyze_evidence",
        evidence_decision,
        {"retry": "retrieve_more", "stop": "finalize"},
    )
    graph.add_edge("retrieve_more", "analyze_evidence")  # the loop edge
    graph.add_edge("finalize", END)
    return graph.compile()


def run_lab_d(scores: list[float]) -> dict:
    """Run Lab D with a scripted sequence of evidence scores."""
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
    # Evidence never clears the threshold -> stops at the cap (no infinite loop).
    capped = run_lab_d([0.20, 0.30, 0.40, 0.40])
    print_trace("Lab D — Iterative retrieval (evidence never improves)", capped)
    print(f"  iterations: {capped['iteration']} (cap={MAX_ITERATIONS})")

    # Evidence clears the threshold on the second pass -> stops early.
    early = run_lab_d([0.40, 0.90])
    print_trace("Lab D — Iterative retrieval (evidence passes)", early)
    print(f"  iterations: {early['iteration']} (stopped early)")
    return capped, early


# ===========================================================================
# Run everything offline.
# ===========================================================================


def main() -> int:
    main_lab_a()
    main_lab_b()
    main_lab_c()
    main_lab_d()
    print("\nAll four labs ran offline with deterministic mocks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
