"""Module 14 solution — the TechCorp Knowledge Agent v1, assembled.

This file is deliberately THIN. The capstone's real deliverable is the shared
package (`src/techcorp_agent/capstone/`) that Modules 15-22 extend; the lab has
you assemble the same graph yourself in `starter/capstone.py`. This solution
demonstrates the punchline: the graph you assembled by hand and the library's
`build_graph` are the *same wiring*, so `build_agent` here simply delegates to
the shared package — and the tests run identical assertions against both.

Run the five required sample interactions offline (no API key):

    TECHCORP_OFFLINE=true uv run python course/14_capstone_v1/solution/capstone.py

Each interaction uses a scripted mock LLM where the LLM's judgment matters
(router intent, grounded answer, abstention) so the offline output is exact and
reproducible; the math and order routes are deterministic via the keyword
fallback and need no script.
"""

from __future__ import annotations

from techcorp_agent.capstone import build_graph, build_offline_store
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT
from techcorp_agent.vectorstore.chroma_store import VectorStore


def build_agent(
    llm: LLMClient,
    store: VectorStore,
    mcp_registry=None,
    max_loops: int = 3,
):
    """Build the capstone agent — by reusing the shared package, not copying it.

    The starter has you wire router -> conditional edges -> route nodes ->
    formatter by hand; this reference shows that the finished assembly IS the
    library graph. One line, because composition already lives in the package.
    """
    return build_graph(llm, store, mcp_registry=mcp_registry, max_loops=max_loops)


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


def _show(title: str, state: dict) -> None:
    print(f"--- {title} ---")
    print(f"Q: {state['question']}")
    print(f"A: {state['answer']}")
    if state.get("sources"):
        print(f"Sources: {', '.join(state['sources'])}")
    print("Trace:")
    for line in state.get("trace", []):
        print(f"  {line}")
    print()


def main() -> int:
    """The five required sample interactions, fully offline."""
    store = build_offline_store()

    # 1) Policy question -> retrieval, cited sources. The scripted client plays
    #    the router ("document_search") and then the grounded answer.
    llm = MockLLMClient(
        responses=[
            "document_search",
            "Yes - employees may work remotely from another country for up to 30 "
            "calendar days per year, with manager approval recorded before travel "
            "and 60 days advance notice; stays longer than 30 days additionally "
            "require joint Legal and HR approval.\nSOURCES: hr-international-remote",
        ]
    )
    app = build_agent(llm, store)
    _show(
        "1) Policy question (retrieval + citation)",
        ask(app, "Can an international employee work remotely from another country?"),
    )

    # 2) Semantic wording difference: "denim" never appears in the dress-code
    #    policy ("jeans", "business casual") and shares no keyword with the
    #    keyword fallback - an LLM router routes it on intent (scripted here),
    #    and hash retrieval still finds hr-dress-code from the overlap on
    #    "wear"/"headquarters".
    llm = MockLLMClient(
        responses=[
            "document_search",
            "Yes - jeans (denim) are allowed at headquarters as long as they are "
            "clean and free of rips, but not during client meetings.\n"
            "SOURCES: hr-dress-code",
        ]
    )
    app = build_agent(llm, store)
    _show(
        "2) Semantic wording difference (denim vs jeans)",
        ask(app, "Am I allowed to wear denim at headquarters?"),
    )

    # 3) Calculator -> deterministic keyword route, local tool offline, and the
    #    formatter never attributes the number to company documents.
    app = build_agent(MockLLMClient(), store)
    _show("3) Calculator (no document attribution)", ask(app, "What is 17.5% of 8,400?"))

    # 4) Order lookup -> orders route; known order answers, unknown order is a
    #    safe message, never a crash. (Local fallback here; the CLI and the
    #    integration test exercise the real MCP servers.)
    app = build_agent(MockLLMClient(), store)
    _show("4a) Order lookup (known order)", ask(app, "What is happening with order TC-1234?"))
    app = build_agent(MockLLMClient(), store)
    _show("4b) Order lookup (unknown order)", ask(app, "What is happening with order TC-9999?"))

    # 5) Unanswerable -> the grounded model abstains instead of inventing policy.
    llm = MockLLMClient(responses=["document_search", f"{ABSTENTION_TEXT}\nSOURCES: none"])
    app = build_agent(llm, store)
    _show(
        "5) Unanswerable (abstention)",
        ask(app, "What is TechCorp's policy for working from the Moon?"),
    )

    print("All five sample interactions ran offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
