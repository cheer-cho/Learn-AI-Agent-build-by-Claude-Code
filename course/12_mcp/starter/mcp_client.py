"""Lab B starter — the MCP client. Fill in the TODOs.

Goal: connect to the calculator server, discover its tools, show their schemas,
call a tool, and handle server + validation errors — all offline.

mcp 2.0 API you need (already imported below):
    - mcp.StdioServerParameters : how to spawn the server (command, args[, cwd]).
      Use `sys.executable` as the command so the spawn is path-independent.
    - mcp.stdio_client(params)  : async context manager -> (read, write) streams.
    - mcp.ClientSession(read, write) : the session. `await session.initialize()`
      runs the handshake; then `list_tools()` and `call_tool(name, args)`.
    - tool.input_schema : the tool's JSON schema (snake_case in mcp 2.0).
    - result.is_error / result.content : a failed call returns is_error=True with
      a text message in content — it does NOT raise. Inspect is_error.

Run it once complete (spawns your calculator_server.py):

    uv run python course/12_mcp/starter/mcp_client.py
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, stdio_client

SERVER_SCRIPT = Path(__file__).resolve().parent / "calculator_server.py"


def server_parameters() -> StdioServerParameters:
    # TODO: Return StdioServerParameters that launch calculator_server.py with
    # this interpreter: command=sys.executable, args=[str(SERVER_SCRIPT)].
    raise NotImplementedError("TODO: build StdioServerParameters")


async def demo() -> None:
    params = server_parameters()

    # TODO (1 — connect): open the server and a session. The pattern is two
    # nested async context managers:
    #     async with stdio_client(params) as (read, write):
    #         async with ClientSession(read, write) as session:
    #             await session.initialize()
    #             ...  # steps 2-5 go here, indented under `session`
    #
    # TODO (2 — list): tools = (await session.list_tools()).tools ; print how
    #   many, and each tool's name + description.
    # TODO (3 — schemas): for each tool, print json.dumps(tool.input_schema,
    #   indent=2) so learners can see the parameter types.
    # TODO (4 — call): call multiply with {"a": 125, "b": 48} and print the
    #   result text (result.content[0].text) — expect "6000.0".
    # TODO (5 — errors): call divide with {"a": 10, "b": 0} and print
    #   result.is_error and the message; then call multiply with a wrong-typed
    #   argument (e.g. {"a": "oops", "b": 2}) and show is_error is True too.
    raise NotImplementedError("TODO: implement the connect/list/schema/call/error flow")


if __name__ == "__main__":
    asyncio.run(demo())
