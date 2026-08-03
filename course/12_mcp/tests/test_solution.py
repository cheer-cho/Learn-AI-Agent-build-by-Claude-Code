"""Module 12 tests — reference solution. Always runs, fully offline.

Drives the solution client helpers (`mcp_session`, `discover_tools`,
`call_tool`) end-to-end against the solution calculator server, which the
client spawns as a stdio subprocess. No network, no API key.

Uses pytest-asyncio in auto mode (configured in pyproject.toml).
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path

MODULE_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client_mod():
    return import_from_path("m12_solution_mcp_client", MODULE_DIR / "solution" / "mcp_client.py")


async def test_discovery_lists_four_tools_with_number_schemas(client_mod):
    params = client_mod.server_parameters()
    async with client_mod.mcp_session(params) as session:
        tools = await client_mod.discover_tools(session)
        by_name = {t.name: t for t in tools}
        assert set(by_name) == {"add", "subtract", "multiply", "divide"}
        for name, tool in by_name.items():
            schema = tool.input_schema
            assert schema["type"] == "object", name
            assert set(schema["properties"]) == {"a", "b"}, name
            assert schema["properties"]["a"]["type"] == "number", name
            assert set(schema["required"]) == {"a", "b"}, name
            assert tool.description, name


async def test_each_operation_computes(client_mod):
    params = client_mod.server_parameters()
    async with client_mod.mcp_session(params) as session:
        cases = [
            ("add", {"a": 2, "b": 3}, "5.0"),
            ("subtract", {"a": 10, "b": 4}, "6.0"),
            ("multiply", {"a": 125, "b": 48}, "6000.0"),
            ("divide", {"a": 9, "b": 2}, "4.5"),
        ]
        for name, args, expected in cases:
            result = await client_mod.call_tool(session, name, args)
            assert result.is_error is False, (name, args)
            assert client_mod.result_text(result) == expected, (name, args)


async def test_divide_by_zero_is_a_tool_error_not_a_crash(client_mod):
    params = client_mod.server_parameters()
    async with client_mod.mcp_session(params) as session:
        result = await client_mod.call_tool(session, "divide", {"a": 10, "b": 0})
        assert result.is_error is True
        assert "divide by zero" in client_mod.result_text(result).lower()
        # server survives and keeps serving
        ok = await client_mod.call_tool(session, "divide", {"a": 8, "b": 4})
        assert ok.is_error is False
        assert client_mod.result_text(ok) == "2.0"


async def test_missing_argument_is_a_validation_error(client_mod):
    params = client_mod.server_parameters()
    async with client_mod.mcp_session(params) as session:
        result = await client_mod.call_tool(session, "add", {"a": 1})  # 'b' missing
        assert result.is_error is True
        text = client_mod.result_text(result).lower()
        assert "validation" in text or "required" in text or "missing" in text


async def test_wrong_typed_argument_is_a_validation_error(client_mod):
    params = client_mod.server_parameters()
    async with client_mod.mcp_session(params) as session:
        result = await client_mod.call_tool(session, "multiply", {"a": "oops", "b": 2})
        assert result.is_error is True
        text = client_mod.result_text(result).lower()
        assert "validation" in text or "number" in text or "parse" in text
