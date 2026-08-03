"""Lab A starter — the calculator MCP server. Fill in the TODOs.

mcp 2.0 API you need (already imported for you below):
    - mcp.server.MCPServer : the high-level server class (mcp 1.x called this
      ``FastMCP``; in the installed mcp 2.0 it is ``MCPServer``).
    - @server.tool(description=...) : decorate a *typed* function to expose it.
      The JSON tool schema is derived automatically from the type hints, so
      annotate every parameter (``a: float``, ``b: float``) and the return type.
    - server.run(transport="stdio") : serve over stdin/stdout.

Run standalone once you finish::

    uv run python course/12_mcp/starter/calculator_server.py

You normally won't run this directly — the client (mcp_client.py) spawns it.
"""

from mcp.server import MCPServer

# The server object clients connect to. The name shows up in the handshake.
server = MCPServer(
    name="techcorp-calculator",
    instructions="A simple arithmetic calculator: add, subtract, multiply, divide.",
)


# TODO: Expose `add`. Decorate the function with `@server.tool(...)` giving a
# clear `description=`, keep the `a: float, b: float` type hints and the
# `-> float` return type, and return `a + b`.
def add(a: float, b: float) -> float:
    raise NotImplementedError("TODO: implement and expose add")


# TODO: Expose `subtract` the same way — description + typed params — and
# return `a - b`.
def subtract(a: float, b: float) -> float:
    raise NotImplementedError("TODO: implement and expose subtract")


# TODO: Expose `multiply` — description + typed params — and return `a * b`.
def multiply(a: float, b: float) -> float:
    raise NotImplementedError("TODO: implement and expose multiply")


# TODO: Expose `divide` — description + typed params — returning `a / b`.
# Guard against b == 0: raise ValueError("Cannot divide by zero: ...") so the
# MCP runtime returns a tool error (is_error=True) instead of crashing the
# server. Do NOT let a ZeroDivisionError escape.
def divide(a: float, b: float) -> float:
    raise NotImplementedError("TODO: implement and expose divide (reject b == 0)")


def main() -> None:
    # TODO: Run the server over stdio: server.run(transport="stdio")
    raise NotImplementedError("TODO: call server.run(transport='stdio')")


if __name__ == "__main__":
    main()
