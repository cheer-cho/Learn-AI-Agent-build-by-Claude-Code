"""Reference solution — the MCP client (Lab B).

An MCP *client* speaks the protocol to one *server*: it starts (or connects to)
the server, runs the initialize handshake, *discovers* the server's tools and
their schemas, *invokes* a chosen tool with arguments, and handles both server
errors (e.g. divide-by-zero) and validation errors (bad/missing arguments).

Run it end-to-end, fully offline — it spawns the solution calculator server
as a child process over stdio and prints discovery + call results::

    uv run python course/12_mcp/solution/mcp_client.py

mcp 2.0 API used (verified against the installed package, version 2.0):
    - mcp.StdioServerParameters : how to spawn a stdio server (command/args/cwd)
    - mcp.stdio_client          : async ctx mgr -> (read, write) streams
    - mcp.ClientSession         : initialize / list_tools / call_tool
    - Tool.input_schema         : the JSON schema (snake_case in mcp 2.0)
    - CallToolResult.is_error / .content / .structured_content
"""

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.types import CallToolResult, Tool

# The calculator server lives right next to this file.
SERVER_SCRIPT = Path(__file__).resolve().parent / "calculator_server.py"


def server_parameters() -> StdioServerParameters:
    """Describe how to launch the calculator server as a stdio subprocess.

    Using ``sys.executable`` (the absolute path to the current interpreter) and
    an absolute script path makes the spawn independent of the caller's working
    directory — important under pytest and CI.
    """
    return StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])


@asynccontextmanager
async def mcp_session(params: StdioServerParameters):
    """Start the server, open a client session, and run the handshake.

    Yields an initialized :class:`mcp.ClientSession`. Both the subprocess and
    the streams are torn down cleanly on exit.
    """
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def discover_tools(session: ClientSession) -> list[Tool]:
    """Return the server's advertised tools (step 2 of the lab)."""
    result = await session.list_tools()
    return list(result.tools)


def format_schema(tool: Tool) -> str:
    """Pretty-print a tool's input JSON schema (step 3 of the lab)."""
    return json.dumps(tool.input_schema, indent=2)


async def call_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Invoke a tool by name with arguments (step 4 of the lab).

    Returns the raw :class:`CallToolResult`. In mcp 2.0 both *server* errors
    (a raised exception inside the tool, e.g. divide-by-zero) and *validation*
    errors (missing/wrong-typed arguments) come back as a normal result with
    ``is_error=True`` and a human-readable message in ``content`` — the server
    process stays alive. That is the "handle errors" path (step 5): inspect
    ``result.is_error`` rather than relying on a raised exception.
    """
    return await session.call_tool(name, arguments)


def result_text(result: CallToolResult) -> str:
    """Extract the text payload from a tool result (works for ok and error)."""
    parts = [block.text for block in result.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts)


async def demo() -> None:
    """Full offline walkthrough: connect, discover, show schemas, call, err."""
    params = server_parameters()
    async with mcp_session(params) as session:
        info = session.server_info
        print(f"Connected to MCP server: {info.name!r}\n")

        # 2 + 3) Discover tools and display their schemas.
        tools = await discover_tools(session)
        print(f"Discovered {len(tools)} tools:")
        for tool in tools:
            print(f"\n  - {tool.name}: {tool.description}")
            print("    input schema:")
            for line in format_schema(tool).splitlines():
                print(f"      {line}")

        # 4) Call a selected tool with arguments.
        print("\n--- Invocation ---")
        for name, args in [
            ("add", {"a": 2, "b": 3}),
            ("multiply", {"a": 125, "b": 48}),
            ("divide", {"a": 9, "b": 2}),
        ]:
            res = await call_tool(session, name, args)
            print(f"{name}({args}) -> {result_text(res)}")

        # 5) Handle a server error (divide-by-zero) and a validation error.
        print("\n--- Error handling ---")
        div0 = await call_tool(session, "divide", {"a": 10, "b": 0})
        print(f"divide by zero -> is_error={div0.is_error}: {result_text(div0)}")

        bad = await call_tool(session, "multiply", {"a": "oops", "b": 2})
        print(f"wrong-typed arg -> is_error={bad.is_error}: {result_text(bad).splitlines()[0]}")

        missing = await call_tool(session, "add", {"a": 1})  # 'b' omitted
        print(
            f"missing arg     -> is_error={missing.is_error}: {result_text(missing).splitlines()[0]}"
        )


if __name__ == "__main__":
    asyncio.run(demo())
