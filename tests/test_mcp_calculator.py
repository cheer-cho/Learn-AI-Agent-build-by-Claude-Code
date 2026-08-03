"""Offline end-to-end tests for the shared calculator MCP server.

These spawn ``techcorp_agent.mcp_servers.calculator_server`` as a real child
process over stdio and drive it with the mcp 2.0 stdio client, exercising the
full discovery -> schema -> invocation -> error path. No network, no API key.

mcp 2.0 API used (verified against the installed package, version 2.0):
    - mcp.StdioServerParameters   (spawn parameters)
    - mcp.stdio_client            (async ctx mgr -> (read, write) streams)
    - mcp.ClientSession           (initialize / list_tools / call_tool)
    - Tool.input_schema           (JSON schema, snake_case in 2.0)
    - CallToolResult.is_error / .content / .structured_content

Robustness: the server is launched with the *absolute* interpreter path
(``sys.executable``) and ``cwd`` pinned to the repository root, so pytest's
working directory cannot break the spawn or the ``techcorp_agent`` import.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

REPO_ROOT = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def calculator_session():
    """Spawn the calculator server over stdio and yield an initialized session."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "techcorp_agent.mcp_servers.calculator_server"],
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def test_lists_all_four_tools_with_schemas():
    async with calculator_session() as session:
        result = await session.list_tools()
        tools = {t.name: t for t in result.tools}

        assert set(tools) == {"add", "subtract", "multiply", "divide"}

        for name, tool in tools.items():
            schema = tool.input_schema
            assert schema["type"] == "object", name
            props = schema["properties"]
            assert set(props) == {"a", "b"}, name
            # Typed float parameters render as JSON schema "number".
            assert props["a"]["type"] == "number", name
            assert props["b"]["type"] == "number", name
            assert set(schema["required"]) == {"a", "b"}, name
            assert tool.description, f"{name} must have a description"


async def test_multiply_returns_product():
    async with calculator_session() as session:
        result = await session.call_tool("multiply", {"a": 125, "b": 48})
        assert result.is_error is False
        assert result.structured_content == {"result": 6000.0}
        assert result.content[0].text == "6000.0"


async def test_add_subtract_divide_happy_path():
    async with calculator_session() as session:
        assert (await session.call_tool("add", {"a": 2, "b": 3})).structured_content == {
            "result": 5.0
        }
        assert (await session.call_tool("subtract", {"a": 10, "b": 4})).structured_content == {
            "result": 6.0
        }
        assert (await session.call_tool("divide", {"a": 9, "b": 2})).structured_content == {
            "result": 4.5
        }


async def test_divide_by_zero_surfaces_as_tool_error():
    """Divide-by-zero must be a protocol error, not a crashed server."""
    async with calculator_session() as session:
        result = await session.call_tool("divide", {"a": 10, "b": 0})
        assert result.is_error is True
        assert "divide by zero" in result.content[0].text.lower()

        # The server is still alive and usable after the error.
        ok = await session.call_tool("divide", {"a": 10, "b": 2})
        assert ok.is_error is False
        assert ok.structured_content == {"result": 5.0}


async def test_missing_argument_surfaces_validation_error():
    async with calculator_session() as session:
        result = await session.call_tool("divide", {"a": 10})  # 'b' missing
        assert result.is_error is True
        text = result.content[0].text.lower()
        assert "validation" in text or "required" in text or "missing" in text


async def test_wrong_typed_argument_surfaces_validation_error():
    async with calculator_session() as session:
        result = await session.call_tool("multiply", {"a": "not-a-number", "b": 2})
        assert result.is_error is True
        text = result.content[0].text.lower()
        assert "validation" in text or "number" in text or "parse" in text


async def test_unknown_tool_surfaces_error():
    async with calculator_session() as session:
        result = await session.call_tool("modulo", {"a": 10, "b": 3})
        assert result.is_error is True
        assert "unknown tool" in result.content[0].text.lower()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
