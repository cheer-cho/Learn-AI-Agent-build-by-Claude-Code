# Module 12 Lab — Build Both Ends of an MCP Connection

## Scenario

TechCorp's agent team keeps reinventing the same helper functions inside every
app. Your lead wants a proof of concept for the fix: expose a capability *once*
as an MCP server, then reach it from a separate client — so the day a second app
needs it, there's nothing to copy. You'll start with the most boring capability
imaginable — a calculator — precisely because it lets you watch every moving
part: discovery, schemas, invocation, and error handling, with no network and no
API key.

You build two programs:

- **Lab A** — `starter/calculator_server.py`: an MCP server exposing `add`,
  `subtract`, `multiply`, `divide`.
- **Lab B** — `starter/mcp_client.py`: a client that connects to that server,
  lists its tools, shows their schemas, calls one, and handles errors.

## Learning objectives

By the end you can:

- Expose typed Python functions as MCP tools with the `mcp` 2.0 `MCPServer` API.
- Make a tool fail *gracefully* (divide-by-zero) so the server returns an error
  instead of crashing.
- Write an async MCP client that runs the initialize handshake over stdio.
- Discover a server's tools and read their JSON schemas.
- Invoke a tool with arguments and distinguish success from `is_error` results.
- Distinguish a Python function, a tool wrapper, an MCP server, an MCP client,
  and an agent using an MCP tool.

## Setup

```bash
uv sync   # if you haven't already
```

Run all commands from the repository root.

- **See the target behavior first:** `uv run python course/12_mcp/solution/mcp_client.py`
- **Run your client (spawns your server):** `uv run python course/12_mcp/starter/mcp_client.py`
- **Test:** `uv run pytest course/12_mcp -q`

Attempt each task before reading the matching solution file.

---

## Lab A — the calculator MCP server

Open `starter/calculator_server.py`. The `MCPServer` object is already created
for you; each tool is a stub raising `NotImplementedError` behind a `# TODO`.

### Task A1 — expose `add`, `subtract`, `multiply`

For each: add the `@server.tool(description="…")` decorator above the function,
keep the `a: float, b: float` type hints and the `-> float` return type (the
schema is derived from them), and return the arithmetic result. Write a real,
specific description — the client and any model read it to choose the tool.

### Task A2 — expose `divide` with a divide-by-zero guard

Same decoration, but before dividing, check `if b == 0:` and
`raise ValueError("Cannot divide by zero: 'b' must be non-zero.")`. Do **not**
let a raw `ZeroDivisionError` escape. The MCP runtime turns your `ValueError`
into a tool result with `is_error=True` — the server keeps running.

### Task A3 — run over stdio

Fill in `main()` to call `server.run(transport="stdio")`. You won't usually run
this directly; the client launches it. But you can smoke-test it exists:

```bash
uv run python course/12_mcp/starter/calculator_server.py
```

It will block silently waiting for a client on stdin — that's correct. Press
`Ctrl-C` to stop. (Real interaction happens in Lab B.)

---

## Lab B — the MCP client

Open `starter/mcp_client.py`.

### Task B1 — describe how to launch the server

Implement `server_parameters()` to return
`StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])`. Using
`sys.executable` (the absolute path to the current interpreter) makes the spawn
independent of your shell's working directory.

### Task B2 — connect and run the handshake

In `demo()`, open the two nested async context managers and initialize:

```python
async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        # everything below is indented under `session`
```

### Task B3 — discover tools and print their schemas

```python
tools = (await session.list_tools()).tools
print(f"Discovered {len(tools)} tools:")
for tool in tools:
    print(f"  - {tool.name}: {tool.description}")
    print(json.dumps(tool.input_schema, indent=2))
```

Note `tool.input_schema` (snake_case in `mcp` 2.0).

### Task B4 — call a tool with arguments

```python
result = await session.call_tool("multiply", {"a": 125, "b": 48})
print(result.content[0].text)  # -> "6000.0"
```

### Task B5 — handle server and validation errors

Call `divide` with `{"a": 10, "b": 0}` and a `multiply` with a wrong-typed
argument (e.g. `{"a": "oops", "b": 2}`). For each, print `result.is_error` and
`result.content[0].text`. Both must show `is_error=True` — and crucially, your
program keeps running through them.

---

## Checkpoints

### Checkpoint A — the server exists and blocks

`uv run python course/12_mcp/starter/calculator_server.py` starts and waits
silently (no traceback). `Ctrl-C` to exit. A `NotImplementedError` here means a
TODO in Lab A is unfinished.

### Checkpoint B — discovery works

Once B1–B3 are done, running the client prints four tools, each with a
number-typed `a`/`b` schema. The reference output (yours should match closely):

```text
Connected to MCP server: 'techcorp-calculator'

Discovered 4 tools:

  - add: Add two numbers and return their sum (a + b).
    input schema:
      {
        "properties": {
          "a": {
            "title": "A",
            "type": "number"
          },
          "b": {
            "title": "B",
            "type": "number"
          }
        },
        "required": [
          "a",
          "b"
        ],
        "type": "object",
        "title": "addArguments"
      }
  ...
```

### Checkpoint C — invocation and error handling

The full reference client run (this is the exact captured output of
`uv run python course/12_mcp/solution/mcp_client.py`, error section):

```text
--- Invocation ---
add({'a': 2, 'b': 3}) -> 5.0
multiply({'a': 125, 'b': 48}) -> 6000.0
divide({'a': 9, 'b': 2}) -> 4.5

--- Error handling ---
divide by zero -> is_error=True: Error executing tool divide: Cannot divide by zero: 'b' must be non-zero.
wrong-typed arg -> is_error=True: Error executing tool multiply: 1 validation error for multiplyArguments
missing arg     -> is_error=True: Error executing tool add: 1 validation error for addArguments
```

The key observation: three failures, zero crashes — each came back as a result
with `is_error=True`, and the program kept going.

### Checkpoint D — tests green

```bash
uv run pytest course/12_mcp -q
```

Expected once your TODOs are gone: everything passes and nothing is skipped.
While TODO markers remain, `test_my_work.py` skips — that skip disappearing is
your progress bar.

---

## Debugging hints

- **`ImportError: cannot import name 'FastMCP'`** → you're on `mcp` 2.0. Import
  `from mcp.server import MCPServer`; `mcp.server.fastmcp` was removed.
- **`AttributeError: 'Tool' object has no attribute 'inputSchema'`** → in `mcp`
  2.0 it's `tool.input_schema` (snake_case).
- **The client hangs forever** → an async pitfall. You either forgot
  `await session.initialize()`, or your code isn't indented *inside* both
  `async with` blocks (the session is only valid within them), or you called an
  `await` coroutine without awaiting it. Also make sure the server's `main()`
  actually calls `server.run(...)` — a stub server accepts the connection but
  advertises nothing.
- **`FileNotFoundError` / server won't spawn** → a path issue. Use
  `command=sys.executable` (not the string `"python"`) and an *absolute*
  `SERVER_SCRIPT` path (`Path(__file__).resolve().parent / "calculator_server.py"`).
- **`RuntimeError: no running event loop`** → call the client through
  `asyncio.run(demo())`, and don't create a second loop inside it.
- **A divide-by-zero *crashes* instead of returning `is_error=True`** → you let a
  `ZeroDivisionError` escape. Guard `if b == 0` and `raise ValueError(...)`
  yourself.
- **Tests skip forever after you finished** → a literal `TODO` string remains in
  a `starter/*.py` file; the gate is literal. Delete the resolved markers.

## Stretch exercise — watch a new tool appear in discovery

Add a fifth tool to your server and confirm the client discovers it with **no
client change** — this is the whole point of discovery.

1. In `starter/calculator_server.py`, add:

   ```python
   @server.tool(description="Raise base to the power exponent (base ** exponent).")
   def power(base: float, exponent: float) -> float:
       return base**exponent
   ```

2. Re-run the client (`uv run python course/12_mcp/starter/mcp_client.py`).
   `power` now shows up in the tool list with its own schema — you changed only
   the *server*, and the client learned about it automatically.
3. Call it: add `("power", {"base": 2, "exponent": 10})` to your invocation list
   and confirm `1024.0`.

Reflect: this is why hosts don't hard-code tool lists. Then consider the flip
side — if *anyone* can add a tool a host will call, why does the host still need
approval and trust controls (concepts §8)?

When everything passes, go through [checklist.md](checklist.md).
