"""A registry that connects *many* MCP servers at once and unifies their tools.

Module 12 connected one client to one server. The moment a host connects two —
a calculator *and* an order server — three new problems appear, and this class
solves each one:

1. **Collisions.** Two servers can advertise a tool with the same name (both a
   ``search`` server and a ``docs`` server might expose ``query``). We give
   every discovered tool a **namespaced** name, ``"<server>.<tool>"`` (e.g.
   ``"calculator.multiply"``, ``"orders.get_order_status"``), so names never
   clash and the namespace tells the registry which session to route a call to.

2. **Partial failure.** With N servers, one being down must not take the others
   with it. :meth:`connect_all` marks a server that fails to spawn as
   *unavailable* and — unless it was registered ``essential=True`` — keeps
   going. The registry serves whatever came up. An *essential* server that
   fails aborts the whole connect, because the host cannot function without it.

3. **Lifecycle.** Each server is a child process plus a stdio session that must
   be spawned, initialized, and later closed cleanly. Each server's context
   managers live in their own :class:`~contextlib.AsyncExitStack`, so one
   server's teardown is independent of the others and a failed spawn leaves no
   dangling process.

Everything here is async and offline: servers are local stdio subprocesses, so
the whole registry — and its tests — run with no network and no API key.

mcp 2.0 API used (verified against the installed package, version 2.0):
    - mcp.StdioServerParameters : how to spawn a stdio server (command/args/cwd)
    - mcp.stdio_client          : async ctx mgr -> (read, write) streams
    - mcp.ClientSession         : initialize / list_tools / call_tool
    - Tool.input_schema         : the JSON schema (snake_case in mcp 2.0)
    - CallToolResult.is_error / .content / .structured_content
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent, Tool

# The separator between a server's namespace and a tool's own name. A tool that
# already contains a dot in its name would be ambiguous, so we split on the
# *first* dot only (see :meth:`MultiServerRegistry.call`).
NAMESPACE_SEP = "."


@dataclass
class ServerHandle:
    """Everything the registry tracks about one registered server.

    ``session`` and ``tools`` are populated by :meth:`connect_all`; they stay
    ``None``/empty for a server that failed to come up. ``available`` is the
    single flag health checks and routing branch on.
    """

    name: str
    params: StdioServerParameters
    essential: bool = False
    available: bool = False
    error: str | None = None
    session: ClientSession | None = None
    tools: list[Tool] = field(default_factory=list)
    _stack: AsyncExitStack | None = None


class RegistryError(Exception):
    """Raised for registry-level misuse (bad namespace, duplicate name, etc.).

    Note this is distinct from a *tool* failure: a tool that errors comes back
    as a ``CallToolResult(is_error=True)`` from :meth:`MultiServerRegistry.call`,
    not as a raised exception. This class is for the registry's own contract.
    """


class MultiServerRegistry:
    """Connect, discover, route, and shut down a set of MCP servers.

    Typical lifecycle::

        registry = MultiServerRegistry()
        registry.register("calculator", calc_params)
        registry.register("orders", order_params)
        await registry.connect_all()          # spawn + initialize both
        registry.discover()                    # build the namespaced tool table
        result = await registry.call("calculator.multiply", {"a": 125, "b": 48})
        await registry.aclose()                # tear every server down

    It is an async context manager, so the common path is::

        async with MultiServerRegistry() as registry:
            registry.register(...); await registry.connect_all(); registry.discover()
            ...
        # aclose() runs on exit
    """

    def __init__(self) -> None:
        self._servers: dict[str, ServerHandle] = {}
        # namespaced tool name -> (server name, Tool)
        self._tools: dict[str, tuple[str, Tool]] = {}

    # -- registration -------------------------------------------------------

    def register(
        self,
        name: str,
        params: StdioServerParameters,
        essential: bool = False,
    ) -> None:
        """Register a server under a namespace ``name`` (not yet connected).

        ``name`` becomes the tool prefix (``"<name>.<tool>"``); it must be
        unique and must not contain the namespace separator. Pass
        ``essential=True`` for a server the host cannot operate without — its
        failure to connect aborts :meth:`connect_all`.
        """
        if not name or NAMESPACE_SEP in name:
            raise RegistryError(
                f"Invalid server name {name!r}: must be non-empty and contain no {NAMESPACE_SEP!r}."
            )
        if name in self._servers:
            raise RegistryError(f"A server named {name!r} is already registered.")
        self._servers[name] = ServerHandle(name=name, params=params, essential=essential)

    # -- connection ---------------------------------------------------------

    async def connect_all(self) -> None:
        """Spawn and initialize every registered server, tolerating failures.

        A server that fails to spawn or initialize is marked ``available=False``
        with its ``error`` recorded, and its partial resources are cleaned up.
        If that server was registered ``essential=True`` the error is re-raised
        (after the whole registry is closed) so the host fails loudly; otherwise
        the registry keeps going with the servers that did come up.
        """
        for handle in self._servers.values():
            if handle.session is not None:  # already connected — idempotent
                continue
            stack = AsyncExitStack()
            try:
                read, write = await stack.enter_async_context(stdio_client(handle.params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
            except BaseException as exc:  # noqa: BLE001 - spawn failures are ExceptionGroups too
                # Clean up whatever partially opened, then record the failure.
                await _safe_aclose(stack)
                handle.available = False
                handle.error = _describe(exc)
                handle.session = None
                handle._stack = None
                if handle.essential:
                    # An essential server is a hard dependency: don't limp on.
                    await self.aclose()
                    raise RegistryError(
                        f"Essential server {handle.name!r} failed to connect: {handle.error}"
                    ) from exc
                continue
            handle.session = session
            handle._stack = stack
            handle.available = True
            handle.error = None

    # -- discovery ----------------------------------------------------------

    def discover(self) -> dict[str, Tool]:
        """Build (and return) the unified, namespaced tool table.

        Every available server is queried at connect time; here we index its
        already-discovered tools under ``"<server>.<tool>"``. Call after
        :meth:`connect_all`. Returns a name -> :class:`Tool` mapping so callers
        can inspect schemas.
        """
        self._tools.clear()
        for handle in self._servers.values():
            if not handle.available:
                continue
            for tool in handle.tools:
                namespaced = f"{handle.name}{NAMESPACE_SEP}{tool.name}"
                self._tools[namespaced] = (handle.name, tool)
        return {name: tool for name, (_, tool) in self._tools.items()}

    async def connect_and_discover(self) -> dict[str, Tool]:
        """Convenience: :meth:`connect_all` then :meth:`discover`."""
        await self.connect_all()
        # list_tools per server has to happen after initialize; do it here so
        # discover() stays a pure indexing step over cached tool lists.
        for handle in self._servers.values():
            if handle.available and handle.session is not None:
                handle.tools = list((await handle.session.list_tools()).tools)
        return self.discover()

    # -- routing ------------------------------------------------------------

    async def call(self, namespaced_name: str, args: dict[str, Any]) -> CallToolResult:
        """Route a namespaced tool call to the owning server and return its result.

        Every failure mode is surfaced as a normal ``CallToolResult`` with
        ``is_error=True`` (never a raised exception), so the caller's control
        loop stays exception-free and the registry never crashes on bad input:

        - a name with no namespace, or an unknown/unavailable server;
        - a tool that isn't advertised by that server;
        - a server that died mid-session (the underlying call raises; we catch
          it, mark the server unavailable, and return a clean error result).
        """
        if NAMESPACE_SEP not in namespaced_name:
            return _error_result(
                f"Tool name {namespaced_name!r} is not namespaced. Use "
                f"'<server>{NAMESPACE_SEP}<tool>', e.g. 'calculator.multiply'."
            )
        server_name, tool_name = namespaced_name.split(NAMESPACE_SEP, 1)

        handle = self._servers.get(server_name)
        if handle is None:
            known = ", ".join(sorted(self._servers)) or "(none registered)"
            return _error_result(
                f"Unknown server namespace {server_name!r}. Known servers: {known}."
            )
        if not handle.available or handle.session is None:
            reason = handle.error or "server is unavailable"
            return _error_result(
                f"Server {server_name!r} is unavailable ({reason}); cannot call "
                f"{namespaced_name!r}."
            )
        if namespaced_name not in self._tools:
            available = ", ".join(sorted(n for n in self._tools if n.startswith(server_name)))
            return _error_result(
                f"Tool {tool_name!r} not found on server {server_name!r}. "
                f"Available: {available or '(none)'}."
            )

        try:
            return await handle.session.call_tool(tool_name, args)
        except BaseException as exc:  # noqa: BLE001 - a dead session raises here
            # The server died mid-session. Mark it down so later calls fail fast,
            # and surface a clean error result rather than crashing the registry.
            handle.available = False
            handle.error = f"session error: {_describe(exc)}"
            return _error_result(
                f"Call to {namespaced_name!r} failed: the server connection is "
                f"broken ({handle.error})."
            )

    # -- introspection ------------------------------------------------------

    def health(self) -> dict[str, dict[str, Any]]:
        """Per-server status snapshot for monitoring / display.

        Each entry reports whether the server is ``available``, whether it was
        ``essential``, its recorded ``error`` (if any), and how many ``tools``
        it currently contributes to the unified table.
        """
        report: dict[str, dict[str, Any]] = {}
        for name, handle in self._servers.items():
            report[name] = {
                "available": handle.available,
                "essential": handle.essential,
                "error": handle.error,
                "tool_count": sum(1 for owner, _ in self._tools.values() if owner == name),
            }
        return report

    def tools(self) -> dict[str, Tool]:
        """Return the current namespaced tool table (name -> Tool)."""
        return {name: tool for name, (_, tool) in self._tools.items()}

    def available_servers(self) -> list[str]:
        """Names of servers that connected successfully."""
        return [name for name, h in self._servers.items() if h.available]

    # -- teardown -----------------------------------------------------------

    async def aclose(self) -> None:
        """Shut every server's session and subprocess down cleanly.

        Safe to call more than once and even if some servers never connected.
        Each server is closed independently, so one server's teardown error
        cannot leak the others' processes.
        """
        for handle in self._servers.values():
            if handle._stack is not None:
                await _safe_aclose(handle._stack)
            handle._stack = None
            handle.session = None
            handle.available = False
        self._tools.clear()

    async def __aenter__(self) -> MultiServerRegistry:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()


# -- module-level helpers ---------------------------------------------------


def _error_result(message: str) -> CallToolResult:
    """Build a ``CallToolResult`` carrying an error message (is_error=True)."""
    return CallToolResult(content=[TextContent(type="text", text=message)], is_error=True)


def _describe(exc: BaseException) -> str:
    """One-line, human-readable description of a (possibly grouped) exception.

    Spawn failures surface as ``ExceptionGroup``s (a nonexistent server script
    exits, closing the pipe); a missing command is a plain ``FileNotFoundError``.
    We flatten either into a short string suitable for a health report.
    """
    if isinstance(exc, BaseExceptionGroup):
        inner = ", ".join(_describe(e) for e in exc.exceptions)
        return inner or exc.__class__.__name__
    text = str(exc).strip()
    return text or exc.__class__.__name__


async def _safe_aclose(stack: AsyncExitStack) -> None:
    """Close an exit stack, swallowing teardown noise from dead subprocesses.

    A subprocess that already exited can make anyio raise on close; the process
    is gone either way, so a clean shutdown of the *registry* must not depend on
    a clean shutdown of a server that already died.
    """
    try:
        await stack.aclose()
    except BaseException:  # noqa: BLE001 - teardown of a dead process is best-effort
        pass
