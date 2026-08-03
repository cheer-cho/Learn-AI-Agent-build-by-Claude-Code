"""A synchronous bridge to the async :class:`MultiServerRegistry`.

The capstone graph nodes are **synchronous** (LangGraph calls them as plain
functions), but the Module 13 MCP registry is **async**, and an MCP stdio
session is bound to the event loop that created it — you cannot connect it on
one loop and call it from another (the streams live on the first loop; a
cross-loop call hangs).

``SyncMCPRegistry`` resolves that mismatch the standard way: it runs **one**
dedicated event loop on a background thread for the registry's whole lifetime,
connects the servers on that loop, and marshals every later call onto the same
loop with :func:`asyncio.run_coroutine_threadsafe`. Graph code then gets a clean
synchronous surface — ``tools()``, ``available_servers()``, ``call()`` — and the
session never leaves its home loop.

This keeps ``build_graph`` free of any event-loop concerns: it just calls
``registry.call(name, args)`` and gets a ``CallToolResult`` back, exactly like
the local tools return a ``ToolResult``.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path
from typing import Any

from mcp import StdioServerParameters
from mcp.types import CallToolResult

from techcorp_agent.config import PROJECT_ROOT
from techcorp_agent.mcp_servers.registry import MultiServerRegistry

# Default servers the capstone connects (the two real Module 13 stdio servers).
DEFAULT_SERVERS = {
    "calculator": "techcorp_agent.mcp_servers.calculator_server",
    "orders": "techcorp_agent.mcp_servers.orders_server",
}


def _server_params(module: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", module],
        cwd=str(PROJECT_ROOT),
    )


class SyncMCPRegistry:
    """Own a background event loop, connect the MCP servers on it, call synchronously.

    Typical use::

        registry = SyncMCPRegistry.connect()      # spawn + discover, or None-ish
        app = build_graph(llm, store, mcp_registry=registry)
        ...
        registry.close()

    :meth:`connect` returns a connected bridge, or ``None`` if no server came up
    (so callers can fall back to local tools). The class is deliberately small:
    the async lifecycle stays inside :class:`MultiServerRegistry`; this only adds
    the loop-thread and the sync marshalling.
    """

    def __init__(self, servers: dict[str, str] | None = None):
        self._servers = servers or DEFAULT_SERVERS
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._registry = MultiServerRegistry()
        self._tools: dict[str, Any] = {}

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _submit(self, coro: Any) -> Any:
        """Run ``coro`` on the background loop and block for its result."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    # -- lifecycle ----------------------------------------------------------

    @classmethod
    def connect(cls, servers: dict[str, str] | None = None) -> SyncMCPRegistry | None:
        """Build a bridge, spawn + discover the servers, and return it.

        Returns ``None`` (after cleaning up the loop thread) if spawning fails or
        no server comes up, so the caller can degrade to local tools.
        """
        bridge = cls(servers)
        try:
            bridge._connect()
        except Exception:  # noqa: BLE001 - any spawn failure -> local fallback
            bridge.close()
            return None
        if not bridge.available_servers():
            bridge.close()
            return None
        return bridge

    def _connect(self) -> None:
        for name, module in self._servers.items():
            self._registry.register(name, _server_params(module))
        self._tools = self._submit(self._registry.connect_and_discover())

    # -- sync surface used by the graph ------------------------------------

    def tools(self) -> dict[str, Any]:
        """Namespaced tool table (name -> Tool), like the async registry's."""
        return dict(self._tools)

    def available_servers(self) -> list[str]:
        return self._registry.available_servers()

    def health(self) -> dict[str, dict[str, Any]]:
        return self._registry.health()

    def call(self, namespaced_name: str, args: dict[str, Any]) -> CallToolResult:
        """Call a namespaced MCP tool synchronously; never raises past here."""
        return self._submit(self._registry.call(namespaced_name, args))

    def close(self) -> None:
        """Tear the registry down on its loop, then stop the loop thread."""
        try:
            if self._loop.is_running():
                self._submit(self._registry.aclose())
        except Exception:  # noqa: BLE001 - teardown of a dead process is best-effort
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        try:
            self._loop.close()
        except Exception:  # noqa: BLE001
            pass


def connect_default_registry() -> SyncMCPRegistry | None:
    """Convenience: connect the two default capstone servers, or ``None``."""
    return SyncMCPRegistry.connect()


def indexed_data_dir() -> Path:
    """The project data directory (handy for callers assembling their own store)."""
    return PROJECT_ROOT / "data"
