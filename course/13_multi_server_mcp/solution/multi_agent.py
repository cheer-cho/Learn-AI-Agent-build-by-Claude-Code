"""Module 13 solution — a multi-server agent.

This agent connects to *two* MCP servers through a
:class:`~techcorp_agent.mcp_servers.registry.MultiServerRegistry` (calculator +
orders), discovers their tools under **namespaced** names, folds in Module 11's
**local** document-search tool, routes each question to the right place, and
returns every answer in one consistent format. It keeps working when the
optional server is killed — the whole point of the essential/nonessential split.

Routing here is a small deterministic rule set, not an LLM call, so the demo is
reproducible and runs fully offline (`TECHCORP_OFFLINE=true`):

- a math question           -> ``calculator.multiply`` (MCP)
- a question about an order  -> ``orders.get_order_status`` (MCP)
- a policy / "can I ..." doc question -> ``document_search`` (LOCAL tool)
- anything ambiguous         -> a clarifying reply (no tool)

The capability decision (which tool) lives in :func:`route`; the transport
decision (which server) lives in the registry. Keeping them separate is what
lets the same agent serve a rule-based router today and an LLM one later.

Run it:
    TECHCORP_OFFLINE=true uv run python course/13_multi_server_mcp/solution/multi_agent.py
"""

from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from mcp import StdioServerParameters

from techcorp_agent.config import get_settings
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.mcp_servers.registry import MultiServerRegistry
from techcorp_agent.tools.search_docs import make_document_search_tool
from techcorp_agent.vectorstore.chroma_store import VectorStore

REPO_ROOT = Path(__file__).resolve().parents[3]

# An order id looks like TC-1234. We route on its presence and pass it as an arg.
_ORDER_ID_RE = re.compile(r"\bTC-\d{3,}\b", re.IGNORECASE)
# A math question we can actually answer with the calculator: "A x B".
_MULTIPLY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:x|\*|multiplied by|times)\s*(\d+(?:\.\d+)?)", re.I)
# Words that signal a policy / document question rather than math or an order.
_DOC_HINTS = ("return", "refund", "warranty", "policy", "damaged", "privacy", "remote", "leave")
# A weather question routes to the OPTIONAL server — which may be down. Routing
# there anyway (and getting a clean "unavailable") is exactly the degradation we
# want to demonstrate.
_WEATHER_HINTS = ("weather", "forecast", "temperature", "rain")


def calculator_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "techcorp_agent.mcp_servers.calculator_server"],
        cwd=str(REPO_ROOT),
    )


def orders_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "techcorp_agent.mcp_servers.orders_server"],
        cwd=str(REPO_ROOT),
    )


def missing_server_params() -> StdioServerParameters:
    """Spawn parameters for an *optional* server that isn't there.

    Used to demonstrate graceful degradation: the interpreter is pointed at a
    script that does not exist, so the child exits immediately and the registry
    marks the server unavailable instead of crashing.
    """
    return StdioServerParameters(
        command=sys.executable,
        args=[str(REPO_ROOT / "no_such_optional_server.py")],
        cwd=str(REPO_ROOT),
    )


@dataclass
class Route:
    """Where a question should go: a tool name plus its arguments.

    ``kind`` is ``"mcp"`` (call the registry with a namespaced name),
    ``"local"`` (run the in-process document-search tool), or ``"none"`` (no
    tool fit — answer with a clarifying message).
    """

    kind: str
    tool: str = ""
    args: dict | None = None
    reason: str = ""


def route(question: str) -> Route:
    """Decide which capability answers ``question`` (the agent's routing job).

    Order matters: a concrete order id or a math expression is unambiguous and
    wins; a policy keyword sends the question to the local docs tool; anything
    else is treated as ambiguous and gets a clarifying reply rather than a
    guessed tool call.
    """
    order = _ORDER_ID_RE.search(question)
    if order:
        return Route("mcp", "orders.get_order_status", {"order_id": order.group(0)})

    mult = _MULTIPLY_RE.search(question)
    if mult:
        a, b = float(mult.group(1)), float(mult.group(2))
        return Route("mcp", "calculator.multiply", {"a": a, "b": b})

    lowered = question.lower()
    if any(word in lowered for word in _WEATHER_HINTS):
        # The registry decides at call time whether this optional server is up;
        # if it's down, the call returns a clean "unavailable" result.
        return Route("mcp", "weather.forecast", {"city": "unknown"})
    if any(word in lowered for word in _DOC_HINTS):
        return Route("local", "document_search", {"query": question})

    return Route("none", reason="no order id, no math expression, no clear policy topic")


def _format(source: str, ok: bool, body: str) -> str:
    """One consistent answer shape regardless of which backend produced it.

    Every reply reads ``[source | ok]  text`` so the calculator, the orders
    server, the local docs tool, and a graceful failure all look the same to the
    caller — the "consistent format" the lab requires.
    """
    status = "ok" if ok else "unavailable"
    return f"[{source} | {status}] {body}"


async def answer(question: str, registry: MultiServerRegistry, doc_tool) -> str:
    """Route one question, invoke the right backend, and format the reply.

    Never raises: an MCP tool error, a down server, or a missing document all
    come back as a formatted ``unavailable`` reply, so the agent loop stays
    exception-free.
    """
    decision = route(question)

    if decision.kind == "mcp":
        result = await registry.call(decision.tool, decision.args or {})
        text = result.content[0].text if result.content else ""
        return _format(decision.tool, not result.is_error, text)

    if decision.kind == "local":
        tool_result = doc_tool.run(decision.args or {})
        body = tool_result.output if tool_result.ok else (tool_result.error or "")
        return _format("document_search", tool_result.ok, body)

    return _format(
        "clarify",
        True,
        "I'm not sure whether that's a math, order, or policy question — could you "
        "add an order id (TC-####), the numbers, or the policy topic?",
    )


def _local_doc_tool():
    """Build the Module 11 local document-search tool over a tiny offline index.

    A hash-embedding store indexed from the mock corpus means `document_search`
    returns real results with no network and no API key — the same trick Module
    11 uses.
    """
    settings = get_settings()
    store = VectorStore(
        HashEmbeddingClient(dimension=256),
        persist_dir=settings.chroma_dir / "m13_demo",
        collection_name="m13_demo",
    )
    if store.count() == 0:
        for doc in load_documents(settings.data_dir):
            store.add_chunks(chunk_document(doc))
    return make_document_search_tool(store)


async def run_demo() -> int:
    """Full offline walkthrough: connect, discover, route, and degrade."""
    doc_tool = _local_doc_tool()

    registry = MultiServerRegistry()
    # Two real servers, plus one *optional* server that will fail to spawn — so
    # we can watch the agent keep working without it (nonessential = degrade).
    registry.register("calculator", calculator_params())
    registry.register("orders", orders_params())
    registry.register("weather", missing_server_params(), essential=False)

    async with registry:
        tools = await registry.connect_and_discover()

        print("=== TechCorp multi-server agent (offline demo) ===\n")
        print("Connected servers and health:")
        for name, status in registry.health().items():
            flag = "up" if status["available"] else f"DOWN ({status['error']})"
            print(f"  - {name:<11} {flag}, tools={status['tool_count']}")
        print(f"\nUnified tool table ({len(tools)} tools):")
        for name in sorted(tools):
            print(f"  - {name}")
        print()

        # The required test prompts, plus one intentionally ambiguous request.
        questions = [
            "What is 125 multiplied by 48?",  # -> calculator (MCP)
            "What is the status of order TC-1234?",  # -> orders (MCP)
            "Can I return a damaged product?",  # -> document_search (LOCAL)
            "What is the status of order TC-9999?",  # -> orders, graceful "no such order"
            "What's the weather where my order is?",  # -> optional server is down
            "Can I do that?",  # -> ambiguous, ask for clarification
        ]
        for question in questions:
            reply = await answer(question, registry, doc_tool)
            print(f"Q: {question}")
            print(f"A: {reply}\n")

    return 0


def main() -> int:
    return asyncio.run(run_demo())


if __name__ == "__main__":
    raise SystemExit(main())
