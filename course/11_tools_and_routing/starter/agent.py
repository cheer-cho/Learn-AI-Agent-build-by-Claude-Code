"""Module 11 starter — a routing research/support agent.

Work through lab.md and replace each TODO. Imports, the tool set, and the
demo scaffolding are wired for you; your job is the routing/answer loop:
choosing a tool, extracting its arguments, running it safely, and phrasing
the result (success OR failure).

Run it:
    TECHCORP_OFFLINE=true uv run python course/11_tools_and_routing/starter/agent.py
Check it:
    uv run pytest course/11_tools_and_routing -q
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
    """Task 2: pull the argument each tool needs out of the raw question.

    - calculator / document_search take the whole question.
    - order_lookup needs the order id (pattern _ORDER_ID_RE); if none is found,
      return empty args on purpose — that drives the missing-argument failure.
    """
    # TODO: Return {"expression": question} for "calculator".
    # TODO: Return {"query": question} for "document_search".
    # TODO: For "order_lookup", search question with _ORDER_ID_RE and return
    #       {"order_id": <match>} if found, else {} (empty — intentional).
    # TODO: Return {} for anything else.
    raise NotImplementedError("extract_args — see lab.md Task 2")


def answer_with_llm(question: str, llm: LLMClient) -> str:
    """Task 4: no tool fit — answer directly with the model."""
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
    """Task 3: route, run, and phrase one question. Must never raise on failure."""
    tool_name = route_question(question, router_llm, tools)

    # TODO: If tool_name == NO_TOOL, return answer_with_llm(question, answer_llm).
    # TODO: Otherwise find the ToolSpec by name, call extract_args(...), then
    #       run it with run_tool(tool, raw_args, timeout_seconds=TOOL_TIMEOUT_SECONDS).
    # TODO: If result.ok, return f"[{tool_name}] {result.output}".
    #       Else return f"[{tool_name} could not help] {result.error}".
    raise NotImplementedError("answer — see lab.md Task 3")


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

    demo = [
        ("What is 125 multiplied by 48?", "calculator"),
        ("What is the status of order TC-1234?", "order_lookup"),
        ("Can I return a damaged product?", "document_search"),
        ("What is the status of order TC-9999?", "order_lookup"),
        ("Can I return it?", "none"),
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
    try:
        raise SystemExit(main())
    except NotImplementedError as exc:
        print(f"\nNot implemented yet: {exc}")
        print("Open course/11_tools_and_routing/lab.md and work through the tasks in order.")
        raise SystemExit(1) from None
