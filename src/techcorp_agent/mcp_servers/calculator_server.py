"""A tiny calculator exposed as an MCP server (arithmetic over stdio).

This is the canonical "hello world" MCP server for the course. It exposes four
typed tools — ``add``, ``subtract``, ``multiply``, ``divide`` — so learners can
watch tool *discovery* and *invocation* happen across a real client/server
boundary without any network or API key. Modules 12, 13, 14, and 22 reuse it.

mcp 2.0 API note
----------------
The installed ``mcp`` package is version 2.0. Its high-level server class is
:class:`mcp.server.MCPServer` (in ``mcp`` 1.x this was ``FastMCP``, imported
from ``mcp.server.fastmcp`` — that path no longer exists). The ergonomics are
the same: decorate a plain typed function with ``@server.tool(...)`` and the
server derives the JSON tool schema from the function's type hints, then serve
it with ``server.run(transport="stdio")``.

Errors (including divide-by-zero) are raised as ordinary Python exceptions.
The MCP runtime catches them and returns a tool result with ``is_error=True``
carrying the message, so a bad call surfaces as a *protocol* error to the
client rather than crashing the server process.

Run standalone::

    uv run python -m techcorp_agent.mcp_servers.calculator_server
"""

from mcp.server import MCPServer

# The server object. ``name`` is what clients see in the initialize handshake
# (server_info) and is handy when several servers are connected at once
# (Module 13). ``instructions`` are optional human-facing guidance a host may
# surface to the model.
server = MCPServer(
    name="techcorp-calculator",
    instructions="A simple arithmetic calculator: add, subtract, multiply, divide.",
)


@server.tool(
    description="Add two numbers and return their sum (a + b).",
)
def add(a: float, b: float) -> float:
    """Return the sum of ``a`` and ``b``."""
    return a + b


@server.tool(
    description="Subtract b from a and return the difference (a - b).",
)
def subtract(a: float, b: float) -> float:
    """Return ``a`` minus ``b``."""
    return a - b


@server.tool(
    description="Multiply two numbers and return their product (a * b).",
)
def multiply(a: float, b: float) -> float:
    """Return the product of ``a`` and ``b``."""
    return a * b


@server.tool(
    description=(
        "Divide a by b and return the quotient (a / b). "
        "Dividing by zero is rejected with an error instead of crashing."
    ),
)
def divide(a: float, b: float) -> float:
    """Return ``a`` divided by ``b``.

    Raises:
        ValueError: if ``b`` is zero. The MCP runtime turns this into a tool
            result with ``is_error=True`` rather than letting the server die.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero: 'b' must be non-zero.")
    return a / b


def main() -> None:
    """Run the calculator server over stdio (blocking)."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
