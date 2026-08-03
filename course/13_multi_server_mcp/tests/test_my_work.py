"""Module 13 tests — your starter implementation.

Auto-skips while `starter/` still contains TODO markers; once you finish the lab
it runs and becomes your completion gate:

    uv run pytest course/13_multi_server_mcp -q

It drives YOUR starter agent's `route` and `answer` against the two real MCP
servers (spawned over stdio) plus the local document-search tool and a
deliberately-down optional server. Fully offline.
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.mcp_servers.registry import MultiServerRegistry

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/ still contains TODO markers — finish the lab first",
)


@pytest.fixture(scope="module")
def agent_mod():
    return import_from_path("m13_starter_multi_agent", STARTER_DIR / "multi_agent.py")


def test_route_math_order_and_ambiguous(agent_mod):
    assert agent_mod.route("What is 125 multiplied by 48?").tool == "calculator.multiply"
    assert agent_mod.route("What is the status of order TC-1234?").tool == "orders.get_order_status"
    assert agent_mod.route("Can I return a damaged product?").kind == "local"
    assert agent_mod.route("Can I do that?").kind == "none"


@pytest.fixture
async def wired(agent_mod):
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


async def test_multiply_and_order_answers(agent_mod, wired):
    registry, doc_tool = wired
    calc = await agent_mod.answer("What is 125 multiplied by 48?", registry, doc_tool)
    assert "6000.0" in calc
    order = await agent_mod.answer("What is the status of order TC-1234?", registry, doc_tool)
    assert "in_transit" in order


async def test_policy_uses_local_tool(agent_mod, wired):
    registry, doc_tool = wired
    reply = await agent_mod.answer("Can I return a damaged product?", registry, doc_tool)
    assert "document_search" in reply


async def test_unknown_order_and_down_server_degrade(agent_mod, wired):
    registry, doc_tool = wired
    bad_order = await agent_mod.answer("What is the status of order TC-9999?", registry, doc_tool)
    assert "unavailable" in bad_order.lower()
    down = await agent_mod.answer("What's the weather right now?", registry, doc_tool)
    assert "unavailable" in down.lower()
    # The good servers are unaffected.
    assert set(registry.available_servers()) == {"calculator", "orders"}
