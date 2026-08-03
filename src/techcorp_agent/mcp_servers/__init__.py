"""Reusable MCP servers for the TechCorp Agent lab course.

These servers are built on the installed ``mcp`` package (version 2.0), which
exposes its high-level server API as :class:`mcp.server.MCPServer` — the
successor to what earlier ``mcp`` 1.x releases called ``FastMCP``. Modules 12,
13, 14, and 22 all reuse the calculator server defined here, so it lives in the
shared library rather than inside a single course module.

Run a server standalone over stdio, e.g.::

    uv run python -m techcorp_agent.mcp_servers.calculator_server
"""
