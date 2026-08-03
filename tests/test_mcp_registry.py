"""Offline tests for the multi-server MCP registry.

These spawn the *real* shared calculator and orders servers as stdio child
processes and drive them through :class:`MultiServerRegistry`, exercising the
full multi-server story: unified namespaced discovery, routing a call to the
right server, graceful tool errors, partial failure (a bogus nonessential
server does not sink the good ones), and the essential-server hard-fail. No
network, no API key.

Robustness mirrors the calculator tests: servers are spawned with the absolute
interpreter path (``sys.executable``) and ``cwd`` pinned to the repo root, so
pytest's working directory can't break the spawn or the package import.

Uses pytest-asyncio in auto mode (configured in pyproject.toml).
"""

import sys
from pathlib import Path

import pytest
from mcp import StdioServerParameters

from techcorp_agent.mcp_servers.registry import MultiServerRegistry, RegistryError

REPO_ROOT = Path(__file__).resolve().parents[1]


def _server(module: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", module],
        cwd=str(REPO_ROOT),
    )


def calculator_params() -> StdioServerParameters:
    return _server("techcorp_agent.mcp_servers.calculator_server")


def orders_params() -> StdioServerParameters:
    return _server("techcorp_agent.mcp_servers.orders_server")


def bogus_params() -> StdioServerParameters:
    """Spawn parameters that point the interpreter at a script that isn't there.

    The child exits immediately, closing the pipe before the handshake — the
    same failure a misconfigured real server would produce.
    """
    return StdioServerParameters(
        command=sys.executable,
        args=[str(REPO_ROOT / "does_not_exist_multi_server.py")],
        cwd=str(REPO_ROOT),
    )


async def _connected_registry() -> MultiServerRegistry:
    registry = MultiServerRegistry()
    registry.register("calculator", calculator_params())
    registry.register("orders", orders_params())
    await registry.connect_and_discover()
    return registry


async def test_unified_discovery_shows_namespaced_tools_from_both_servers():
    registry = await _connected_registry()
    try:
        tools = registry.tools()
        # Every tool is namespaced by its owning server, so names never collide.
        assert "calculator.add" in tools
        assert "calculator.multiply" in tools
        assert "orders.get_order_status" in tools
        assert "orders.list_recent_orders" in tools
        # Namespacing is what prevents a collision: bare names would clash if two
        # servers shared one; here each name carries its origin.
        assert all("." in name for name in tools)
        # Schemas survive the trip (snake_case input_schema in mcp 2.0).
        assert tools["calculator.multiply"].input_schema["type"] == "object"
    finally:
        await registry.aclose()


async def test_health_reports_both_servers_available():
    registry = await _connected_registry()
    try:
        health = registry.health()
        assert health["calculator"]["available"] is True
        assert health["orders"]["available"] is True
        assert health["calculator"]["tool_count"] == 4
        assert health["orders"]["tool_count"] == 2
    finally:
        await registry.aclose()


async def test_routes_calculator_multiply_to_the_calculator_server():
    registry = await _connected_registry()
    try:
        result = await registry.call("calculator.multiply", {"a": 125, "b": 48})
        assert result.is_error is False
        assert result.structured_content == {"result": 6000.0}
    finally:
        await registry.aclose()


async def test_routes_order_status_and_returns_in_transit():
    registry = await _connected_registry()
    try:
        result = await registry.call("orders.get_order_status", {"order_id": "TC-1234"})
        assert result.is_error is False
        assert result.structured_content["status"] == "in_transit"
    finally:
        await registry.aclose()


async def test_unknown_order_surfaces_a_clean_tool_error():
    registry = await _connected_registry()
    try:
        result = await registry.call("orders.get_order_status", {"order_id": "TC-9999"})
        assert result.is_error is True
        assert "no order found" in result.content[0].text.lower()
        # The registry (and the orders server) survive the error and keep serving.
        ok = await registry.call("orders.get_order_status", {"order_id": "TC-1234"})
        assert ok.is_error is False
    finally:
        await registry.aclose()


async def test_unknown_namespace_is_a_clean_error_not_a_crash():
    registry = await _connected_registry()
    try:
        result = await registry.call("weather.forecast", {"city": "London"})
        assert result.is_error is True
        assert "unknown server namespace" in result.content[0].text.lower()
    finally:
        await registry.aclose()


async def test_unnamespaced_name_is_rejected_cleanly():
    registry = await _connected_registry()
    try:
        result = await registry.call("multiply", {"a": 2, "b": 2})
        assert result.is_error is True
        assert "not namespaced" in result.content[0].text.lower()
    finally:
        await registry.aclose()


async def test_tool_not_found_on_known_server_is_a_clean_error():
    registry = await _connected_registry()
    try:
        result = await registry.call("calculator.exponentiate", {"a": 2, "b": 8})
        assert result.is_error is True
        assert "not found" in result.content[0].text.lower()
    finally:
        await registry.aclose()


async def test_bogus_nonessential_server_does_not_sink_the_good_ones():
    registry = MultiServerRegistry()
    registry.register("calculator", calculator_params())
    registry.register("orders", orders_params())
    registry.register("weather", bogus_params(), essential=False)  # will fail to spawn
    try:
        await registry.connect_and_discover()  # must NOT raise

        health = registry.health()
        assert health["weather"]["available"] is False
        assert health["weather"]["error"]  # a reason was recorded
        assert health["calculator"]["available"] is True
        assert health["orders"]["available"] is True

        # The good servers still serve calls.
        calc = await registry.call("calculator.multiply", {"a": 125, "b": 48})
        assert calc.structured_content == {"result": 6000.0}
        order = await registry.call("orders.get_order_status", {"order_id": "TC-1234"})
        assert order.structured_content["status"] == "in_transit"

        # Calling the dead server is a clean error, not a crash.
        down = await registry.call("weather.forecast", {})
        assert down.is_error is True
        assert "unavailable" in down.content[0].text.lower()
    finally:
        await registry.aclose()


async def test_bogus_essential_server_aborts_connect():
    registry = MultiServerRegistry()
    registry.register("calculator", calculator_params())
    registry.register("weather", bogus_params(), essential=True)  # hard dependency
    with pytest.raises(RegistryError, match="[Ee]ssential"):
        await registry.connect_and_discover()
    # Registry cleaned up after the abort; nothing left available.
    assert registry.available_servers() == []


def test_duplicate_registration_is_rejected():
    registry = MultiServerRegistry()
    registry.register("calculator", calculator_params())
    with pytest.raises(RegistryError, match="already registered"):
        registry.register("calculator", calculator_params())


def test_bad_namespace_name_is_rejected():
    registry = MultiServerRegistry()
    with pytest.raises(RegistryError):
        registry.register("calc.ulator", calculator_params())  # contains the separator


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
