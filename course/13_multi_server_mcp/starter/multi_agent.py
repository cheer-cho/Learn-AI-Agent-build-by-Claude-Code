"""Module 13 lab — a multi-server agent (starter).

Build an agent that connects to *two* MCP servers through a
:class:`~techcorp_agent.mcp_servers.registry.MultiServerRegistry` (calculator +
orders), discovers their tools under **namespaced** names, folds in Module 11's
**local** document-search tool, routes each question to the right place, and
returns every answer in one consistent format — while staying up when the
optional server is down.

Fill in every ``# TODO``. The registry, both servers, and the local doc tool
already exist in the shared library — you are wiring, not reinventing. Routing
is a small deterministic rule set (no LLM) so your run is reproducible and fully
offline.

Run it:
    TECHCORP_OFFLINE=true uv run python course/13_multi_server_mcp/starter/multi_agent.py

The tests in tests/test_my_work.py stay skipped until every TODO marker is gone.
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

_ORDER_ID_RE = re.compile(r"\bTC-\d{3,}\b", re.IGNORECASE)
_MULTIPLY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:x|\*|multiplied by|times)\s*(\d+(?:\.\d+)?)", re.I)
_DOC_HINTS = ("return", "refund", "warranty", "policy", "damaged", "privacy", "remote", "leave")
_WEATHER_HINTS = ("weather", "forecast", "temperature", "rain")


def _stdio(module: str) -> StdioServerParameters:
    """Spawn parameters for a server module, cwd pinned to the repo root."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", module],
        cwd=str(REPO_ROOT),
    )


def calculator_params() -> StdioServerParameters:
    return _stdio("techcorp_agent.mcp_servers.calculator_server")


def orders_params() -> StdioServerParameters:
    return _stdio("techcorp_agent.mcp_servers.orders_server")


def missing_server_params() -> StdioServerParameters:
    """An *optional* server that isn't there — used to demonstrate degradation."""
    return StdioServerParameters(
        command=sys.executable,
        args=[str(REPO_ROOT / "no_such_optional_server.py")],
        cwd=str(REPO_ROOT),
    )


@dataclass
class Route:
    """Where a question goes: kind is 'mcp', 'local', or 'none'."""

    kind: str
    tool: str = ""
    args: dict | None = None
    reason: str = ""


def route(question: str) -> Route:
    """Decide which capability answers ``question``.

    Return, in priority order:
      - an order id present  -> Route("mcp", "orders.get_order_status", {"order_id": ...})
      - a multiply pattern   -> Route("mcp", "calculator.multiply", {"a": ..., "b": ...})
      - a weather hint       -> Route("mcp", "weather.forecast", {"city": "unknown"})
      - a doc/policy hint     -> Route("local", "document_search", {"query": question})
      - otherwise             -> Route("none", reason="...")
    """
    order = _ORDER_ID_RE.search(question)
    if order:
        # TODO: return an "mcp" Route to "orders.get_order_status" with the order id.
        raise NotImplementedError("route: order-id case")

    mult = _MULTIPLY_RE.search(question)
    if mult:
        a, b = float(mult.group(1)), float(mult.group(2))
        # TODO: return an "mcp" Route to "calculator.multiply" with args {"a": a, "b": b}.
        raise NotImplementedError("route: multiply case")

    lowered = question.lower()
    if any(word in lowered for word in _WEATHER_HINTS):
        # TODO: return an "mcp" Route to "weather.forecast" (the optional server).
        raise NotImplementedError("route: weather case")
    if any(word in lowered for word in _DOC_HINTS):
        # TODO: return a "local" Route to "document_search" with {"query": question}.
        raise NotImplementedError("route: document case")

    # TODO: no tool fit — return Route("none", reason="...").
    raise NotImplementedError("route: ambiguous case")


def _format(source: str, ok: bool, body: str) -> str:
    """One consistent answer shape: ``[source | ok|unavailable] body``."""
    status = "ok" if ok else "unavailable"
    return f"[{source} | {status}] {body}"


async def answer(question: str, registry: MultiServerRegistry, doc_tool) -> str:
    """Route one question, invoke the right backend, and format the reply.

    Must never raise: an MCP tool error, a down server, or a missing document
    should all come back as a formatted 'unavailable' reply.
    """
    decision = route(question)

    if decision.kind == "mcp":
        # TODO: await registry.call(decision.tool, decision.args or {}); pull the
        # text from result.content[0].text (if any) and return _format(...,
        # not result.is_error, text).
        raise NotImplementedError("answer: mcp branch")

    if decision.kind == "local":
        # TODO: run the local tool: tool_result = doc_tool.run(decision.args or {});
        # return _format("document_search", tool_result.ok, output-or-error).
        raise NotImplementedError("answer: local branch")

    # TODO: ambiguous — return a formatted clarifying message (ok=True).
    raise NotImplementedError("answer: none branch")


def _local_doc_tool():
    """Module 11's local document-search tool over a tiny offline hash index."""
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
    doc_tool = _local_doc_tool()

    registry = MultiServerRegistry()
    # TODO: register "calculator" and "orders" (both real), plus an optional
    # "weather" server via missing_server_params() with essential=False.
    raise NotImplementedError("run_demo: register servers")

    async with registry:  # noqa: F841 - kept as a hint for the intended shape
        # TODO: tools = await registry.connect_and_discover()
        # TODO: print each server's health (registry.health()) and the tool table.
        # TODO: loop the questions below through answer() and print Q/A pairs.
        questions = [
            "What is 125 multiplied by 48?",
            "What is the status of order TC-1234?",
            "Can I return a damaged product?",
            "What is the status of order TC-9999?",
            "What's the weather where my order is?",
            "Can I do that?",  # intentionally ambiguous
        ]
        raise NotImplementedError("run_demo: connect, discover, and answer")

    return 0


def main() -> int:
    return asyncio.run(run_demo())


if __name__ == "__main__":
    raise SystemExit(main())
