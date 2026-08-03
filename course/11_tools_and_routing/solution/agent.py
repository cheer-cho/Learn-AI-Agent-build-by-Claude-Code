"""Module 11 solution — a routing research/support agent.

The agent answers each question by (1) choosing a tool with the router, (2)
extracting the tool's arguments, (3) running the tool safely, and (4) turning
the tool result — success OR failure — into a user-facing reply. Questions that
fit no tool are answered by the LLM directly.

Runs fully offline. The router LLM is scripted so the demo is deterministic;
the calculator, order lookup, and document search run for real against mock
data and a temporary hash-embedding index.

Run it:
    TECHCORP_OFFLINE=true uv run python course/11_tools_and_routing/solution/agent.py
"""

import re

from techcorp_agent.config import get_settings
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage
from techcorp_agent.tools import (
    NO_TOOL,
    ToolResult,
    ToolSpec,
    make_calculator_tool,
    make_document_search_tool,
    make_order_lookup_tool,
    route_question,
    run_tool,
)
from techcorp_agent.vectorstore.chroma_store import VectorStore

_ORDER_ID_RE = re.compile(r"\bTC-\d{3,}\b", re.IGNORECASE)

TOOL_TIMEOUT_SECONDS = 5.0


def extract_args(tool_name: str, question: str) -> dict:
    """Pull the argument each tool needs out of the raw question.

    Deliberately simple: the calculator and document search take the whole
    question; order lookup needs the order id, which we find by pattern. A
    missing id yields empty args on purpose — that exercises the missing-argument
    failure path (the tool returns a validation failure, not a crash).
    """
    if tool_name == "calculator":
        return {"expression": question}
    if tool_name == "document_search":
        return {"query": question}
    if tool_name == "order_lookup":
        match = _ORDER_ID_RE.search(question)
        return {"order_id": match.group(0)} if match else {}
    return {}


def answer_with_llm(question: str, llm: LLMClient) -> str:
    """No tool fit — answer directly with the model (general explanations, chat)."""
    messages = [
        ChatMessage(role="system", content="You are TechCorp's helpful support assistant."),
        ChatMessage(role="user", content=question),
    ]
    return llm.complete(messages).content


def answer(
    question: str,
    router_llm: LLMClient,
    answer_llm: LLMClient,
    tools: list[ToolSpec],
) -> str:
    """Route, run, and phrase one question. Never raises on a tool failure."""
    tool_name = route_question(question, router_llm, tools)
    if tool_name == NO_TOOL:
        return answer_with_llm(question, answer_llm)

    by_name = {tool.name: tool for tool in tools}
    tool = by_name[tool_name]
    raw_args = extract_args(tool_name, question)
    result: ToolResult = run_tool(tool, raw_args, timeout_seconds=TOOL_TIMEOUT_SECONDS)

    if result.ok:
        return f"[{tool_name}] {result.output}"
    # Tool failed (bad args, no data, raised, timed out) — surface it, don't crash.
    return f"[{tool_name} could not help] {result.error}"


def build_tools(store: VectorStore) -> list[ToolSpec]:
    return [
        make_calculator_tool(),
        make_order_lookup_tool(),
        make_document_search_tool(store),
    ]


def _demo_corpus_store() -> VectorStore:
    """A tiny in-repo index so document_search returns something offline."""
    settings = get_settings()
    store = VectorStore(
        HashEmbeddingClient(dimension=256),
        persist_dir=settings.chroma_dir / "m11_demo",
        collection_name="m11_demo",
    )
    if store.count() == 0:
        for doc in load_documents(settings.data_dir):
            store.add_chunks(chunk_document(doc))
    return store


def main() -> int:
    store = _demo_corpus_store()
    tools = build_tools(store)

    # A demo set covering every route plus the graceful-failure and ambiguous
    # paths. The router LLM is scripted (one reply per question, in order) so the
    # run is deterministic; the tools themselves run for real.
    demo = [
        ("What is 125 multiplied by 48?", "calculator"),
        ("What is the status of order TC-1234?", "order_lookup"),
        ("Can I return a damaged product?", "document_search"),
        ("What is the status of order TC-9999?", "order_lookup"),
        ("Can I return it?", "none"),  # ambiguous: no order id, no clear topic
    ]
    router_llm = MockLLMClient(responses=[route for _, route in demo])
    answer_llm = MockLLMClient(
        responses=["Could you tell me which item or order you mean? I can then check."]
    )

    print("=== TechCorp routing agent (offline demo) ===\n")
    for question, _ in demo:
        reply = answer(question, router_llm, answer_llm, tools)
        print(f"Q: {question}")
        print(f"A: {reply}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
