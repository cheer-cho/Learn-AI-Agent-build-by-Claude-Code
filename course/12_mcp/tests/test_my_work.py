"""Module 12 tests — your starter implementation.

Auto-skips while `starter/` still contains TODO markers; once you finish both
labs it runs and becomes your completion gate:

    uv run pytest course/12_mcp -q

It spawns YOUR starter/calculator_server.py over stdio and checks discovery,
each operation, and the two error paths. It also checks that your client's
`server_parameters()` returns valid spawn parameters. It intentionally does not
dictate the internal shape of your client's `demo()`.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

from techcorp_agent.course_utils import import_from_path, starter_incomplete

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/ still contains TODO markers — finish both labs first",
)


@asynccontextmanager
async def starter_session():
    """Spawn the learner's starter calculator server and yield a session."""
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(STARTER_DIR / "calculator_server.py")],
        cwd=str(MODULE_DIR.parents[1]),  # repo root
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _text(result) -> str:
    return "\n".join(b.text for b in result.content if getattr(b, "type", None) == "text")


def test_client_server_parameters_are_valid():
    client_mod = import_from_path("m12_starter_mcp_client", STARTER_DIR / "mcp_client.py")
    params = client_mod.server_parameters()
    assert isinstance(params, StdioServerParameters)
    assert params.command == sys.executable
    assert any("calculator_server.py" in str(a) for a in params.args)


async def test_starter_server_exposes_four_tools():
    async with starter_session() as session:
        tools = {t.name: t for t in (await session.list_tools()).tools}
        assert set(tools) == {"add", "subtract", "multiply", "divide"}
        for name, tool in tools.items():
            assert set(tool.input_schema["properties"]) == {"a", "b"}, name
            assert tool.input_schema["properties"]["a"]["type"] == "number", name
            assert tool.description, name


async def test_starter_operations_compute():
    async with starter_session() as session:
        assert _text(await session.call_tool("add", {"a": 2, "b": 3})) == "5.0"
        assert _text(await session.call_tool("subtract", {"a": 10, "b": 4})) == "6.0"
        assert _text(await session.call_tool("multiply", {"a": 125, "b": 48})) == "6000.0"
        assert _text(await session.call_tool("divide", {"a": 9, "b": 2})) == "4.5"


async def test_starter_divide_by_zero_is_error_not_crash():
    async with starter_session() as session:
        result = await session.call_tool("divide", {"a": 10, "b": 0})
        assert result.is_error is True
        assert "zero" in _text(result).lower()
        ok = await session.call_tool("add", {"a": 1, "b": 1})  # still alive
        assert _text(ok) == "2.0"


async def test_starter_validation_error_on_bad_argument():
    async with starter_session() as session:
        result = await session.call_tool("multiply", {"a": "oops", "b": 2})
        assert result.is_error is True
