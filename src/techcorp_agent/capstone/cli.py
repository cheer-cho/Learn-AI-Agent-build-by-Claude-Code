"""Command-line interface for the TechCorp Knowledge Agent v1.

Run it:

    # One-shot, offline, with the dev trace and local tools (no MCP servers):
    TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone.cli \
        --question "What is 17.5% of 8,400?" --dev --no-mcp

    # Interactive REPL (Ctrl-D / 'exit' to quit):
    uv run python -m techcorp_agent.capstone.cli

Two display modes:

- **user mode** (default) hides internals — you see only the answer and its
  sources, the way a pilot user would;
- **dev mode** (``--dev``) additionally prints the LangGraph ``trace`` after each
  answer, so you can see which node ran and why.

MCP: by default the CLI spawns the calculator + orders MCP servers (Module 13)
and routes math/order questions to them. ``--no-mcp`` skips the spawn and uses
the in-process local tools instead; the CLI also **auto-falls back** to local
tools if spawning fails, so a broken MCP setup never blocks the agent.

Conversation identity: a ``--conversation-id`` is generated (uuid4) when absent,
displayed once, and used to key a **per-conversation in-memory history list**.
Note: this history is intentionally *in-memory only* — durable, checkpointed
persistence across process restarts is Module 15's job (SQLite checkpointer);
v1 forgets everything when the process exits, and that is by design.
"""

from __future__ import annotations

import argparse
import uuid
from typing import Any

from techcorp_agent.capstone import build_graph, build_offline_store
from techcorp_agent.capstone.mcp_bridge import SyncMCPRegistry
from techcorp_agent.config import get_settings
from techcorp_agent.llm.factory import get_llm_client


def _make_mcp_registry() -> SyncMCPRegistry | None:
    """Spawn and connect the calculator + orders MCP servers, or return ``None``.

    Reuses the Module 13 registry through the :class:`SyncMCPRegistry` bridge,
    which owns a background event loop so the sync graph can call the async
    servers safely. Any failure to spawn/connect (bad interpreter, missing
    module, sandbox) yields ``None`` so the CLI cleanly falls back to local
    tools — the graceful-degradation contract from Modules 11 and 13.
    """
    return SyncMCPRegistry.connect()


def _close_registry(registry: SyncMCPRegistry | None) -> None:
    if registry is not None:
        registry.close()


def _answer(app: Any, question: str, conversation_id: str) -> dict:
    """Invoke the compiled graph for one question and return the final state."""
    return app.invoke(
        {
            "conversation_id": conversation_id,
            "question": question,
            "trace": [],
            "loop_count": 0,
        }
    )


def _print_result(state: dict, dev: bool) -> None:
    """Render one answer. User mode hides the trace; dev mode shows it."""
    print(f"\nAgent: {state.get('answer', '').strip()}")
    sources = state.get("sources") or []
    if sources:
        print(f"Sources: {', '.join(sources)}")
    if dev:
        print("\n[dev] trace:")
        for line in state.get("trace", []):
            print(f"  {line}")
        print(f"[dev] route: {state.get('route')}")


def run(
    question: str | None,
    *,
    dev: bool = False,
    conversation_id: str | None = None,
    use_mcp: bool = True,
) -> int:
    """Drive the agent once (``question`` given) or as a REPL (``question`` None)."""
    settings = get_settings()
    llm = get_llm_client(settings)
    store = build_offline_store()

    registry = _make_mcp_registry() if use_mcp else None
    if use_mcp and registry is None:
        print("[info] MCP servers unavailable — using local calculator/order tools.")

    conversation_id = conversation_id or str(uuid.uuid4())
    # Per-conversation history, in-memory only (Module 15 adds durable memory).
    history: list[dict[str, str]] = []

    print(f"TechCorp Knowledge Agent v1  (conversation {conversation_id})")
    print(f"mode: {'dev' if dev else 'user'} | mcp: {'on' if registry else 'off (local tools)'}")

    try:
        app = build_graph(llm, store, mcp_registry=registry)

        if question is not None:
            state = _answer(app, question, conversation_id)
            history.append({"question": question, "answer": state.get("answer", "")})
            _print_result(state, dev)
            return 0

        print("Type a question, or 'exit' / Ctrl-D to quit.\n")
        while True:
            try:
                line = input("You: ").strip()
            except EOFError:
                print()
                break
            if not line:
                continue
            if line.lower() in {"exit", "quit"}:
                break
            state = _answer(app, line, conversation_id)
            history.append({"question": line, "answer": state.get("answer", "")})
            _print_result(state, dev)
            print()
        print(f"\nConversation {conversation_id} had {len(history)} turn(s). Goodbye.")
        return 0
    finally:
        _close_registry(registry)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="techcorp-capstone",
        description="TechCorp Knowledge Agent v1 — offline-capable RAG + tools + MCP agent.",
    )
    parser.add_argument(
        "--question",
        "-q",
        help="Ask one question and exit (one-shot). Omit for an interactive REPL.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Developer mode: print the LangGraph trace after each answer.",
    )
    parser.add_argument(
        "--conversation-id",
        help="Reuse a conversation id (a uuid4 is generated and shown when omitted).",
    )
    parser.add_argument(
        "--no-mcp",
        action="store_true",
        help="Skip spawning MCP servers; use the in-process local tools instead.",
    )
    args = parser.parse_args(argv)
    return run(
        args.question,
        dev=args.dev,
        conversation_id=args.conversation_id,
        use_mcp=not args.no_mcp,
    )


if __name__ == "__main__":
    raise SystemExit(main())
