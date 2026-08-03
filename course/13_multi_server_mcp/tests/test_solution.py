"""Module 13 tests — reference solution. Always runs, fully offline.

Drives the solution multi-agent's routing and its live registry against the two
real MCP servers (calculator + orders) spawned as stdio subprocesses, plus the
in-process document-search tool and a deliberately-down optional server. No
network, no API key.

Uses pytest-asyncio in auto mode (configured in pyproject.toml).
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path
from techcorp_agent.mcp_servers.registry import MultiServerRegistry

MODULE_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def agent_mod():
    return import_from_path("m13_solution_multi_agent", MODULE_DIR / "solution" / "multi_agent.py")


# -- routing (pure, no servers) --------------------------------------------


def test_route_sends_math_to_calculator(agent_mod):
    decision = agent_mod.route("What is 125 multiplied by 48?")
    assert decision.kind == "mcp"
    assert decision.tool == "calculator.multiply"
    assert decision.args == {"a": 125.0, "b": 48.0}


def test_route_sends_order_to_orders_server(agent_mod):
    decision = agent_mod.route("What is the status of order TC-1234?")
    assert decision.kind == "mcp"
    assert decision.tool == "orders.get_order_status"
    assert decision.args == {"order_id": "TC-1234"}


def test_route_sends_policy_to_local_document_search(agent_mod):
    decision = agent_mod.route("Can I return a damaged product?")
    assert decision.kind == "local"
    assert decision.tool == "document_search"


def test_route_ambiguous_question_picks_no_tool(agent_mod):
    decision = agent_mod.route("Can I do that?")
    assert decision.kind == "none"


# -- end-to-end through a live registry ------------------------------------


@pytest.fixture
async def wired(agent_mod):
    """A live registry (calculator + orders + a down optional) and the doc tool."""
    doc_tool = agent_mod._local_doc_tool()
    registry = MultiServerRegistry()
    registry.register("calculator", agent_mod.calculator_params())
    registry.register("orders", agent_mod.orders_params())
    registry.register("weather", agent_mod.missing_server_params(), essential=False)
    await registry.connect_and_discover()
    try:
        yield registry, doc_tool
    finally:
        await registry.aclose()


async def test_unified_table_has_namespaced_tools_from_both_servers(wired):
    registry, _ = wired
    tools = registry.tools()
    assert "calculator.multiply" in tools
    assert "orders.get_order_status" in tools
    assert all("." in name for name in tools)


async def test_answer_multiply_via_mcp(agent_mod, wired):
    registry, doc_tool = wired
    reply = await agent_mod.answer("What is 125 multiplied by 48?", registry, doc_tool)
    assert "calculator.multiply | ok" in reply
    assert "6000.0" in reply


async def test_answer_order_status_via_mcp(agent_mod, wired):
    registry, doc_tool = wired
    reply = await agent_mod.answer("What is the status of order TC-1234?", registry, doc_tool)
    assert "orders.get_order_status | ok" in reply
    assert "in_transit" in reply


async def test_answer_policy_via_local_tool(agent_mod, wired):
    registry, doc_tool = wired
    reply = await agent_mod.answer("Can I return a damaged product?", registry, doc_tool)
    assert "document_search | ok" in reply
    assert reply.strip()  # some retrieved text came back


async def test_answer_unknown_order_degrades_gracefully(agent_mod, wired):
    registry, doc_tool = wired
    reply = await agent_mod.answer("What is the status of order TC-9999?", registry, doc_tool)
    assert "unavailable" in reply
    assert "no order found" in reply.lower()


async def test_answer_optional_server_down_is_clean(agent_mod, wired):
    registry, doc_tool = wired
    # The weather server was registered but failed to spawn; the agent stays up.
    assert registry.health()["weather"]["available"] is False
    reply = await agent_mod.answer("What's the weather right now?", registry, doc_tool)
    assert "unavailable" in reply.lower()


async def test_answer_ambiguous_asks_for_clarification(agent_mod, wired):
    registry, doc_tool = wired
    reply = await agent_mod.answer("Can I do that?", registry, doc_tool)
    assert "clarify | ok" in reply


async def test_good_servers_survive_the_down_optional(wired):
    registry, _ = wired
    assert set(registry.available_servers()) == {"calculator", "orders"}
    result = await registry.call("calculator.multiply", {"a": 6, "b": 7})
    assert result.is_error is False
    assert result.structured_content == {"result": 42.0}
