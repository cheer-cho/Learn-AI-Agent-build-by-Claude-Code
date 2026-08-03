"""Reference solution — the calculator MCP server (Lab A).

This is a self-contained copy of the server so the module runs on its own. The
identical, reusable version lives in the shared library at
``src/techcorp_agent/mcp_servers/calculator_server.py`` (imported by later
modules); here it is spelled out in full so learners can read every line.

mcp 2.0 API note: the high-level server class is ``mcp.server.MCPServer``
(the successor to ``FastMCP`` from mcp 1.x). Decorate a typed function with
``@server.tool(...)`` and the JSON schema is derived from the type hints.

Run standalone::

    uv run python course/12_mcp/solution/calculator_server.py
"""

from mcp.server import MCPServer

server = MCPServer(
    name="techcorp-calculator",
    instructions="A simple arithmetic calculator: add, subtract, multiply, divide.",
)


@server.tool(description="Add two numbers and return their sum (a + b).")
def add(a: float, b: float) -> float:
    """Return the sum of ``a`` and ``b``."""
    return a + b


@server.tool(description="Subtract b from a and return the difference (a - b).")
def subtract(a: float, b: float) -> float:
    """Return ``a`` minus ``b``."""
    return a - b


@server.tool(description="Multiply two numbers and return their product (a * b).")
def multiply(a: float, b: float) -> float:
    """Return the product of ``a`` and ``b``."""
    return a * b


@server.tool(
    description=(
        "Divide a by b and return the quotient (a / b). "
        "Dividing by zero is rejected with an error instead of crashing."
    )
)
def divide(a: float, b: float) -> float:
    """Return ``a`` divided by ``b`` (raises ValueError if ``b`` is zero)."""
    if b == 0:
        raise ValueError("Cannot divide by zero: 'b' must be non-zero.")
    return a / b


def main() -> None:
    """Run the calculator server over stdio (blocking)."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
