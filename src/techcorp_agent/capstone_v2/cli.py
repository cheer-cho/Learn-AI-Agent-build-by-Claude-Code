"""Command-line interface for the TechCorp Knowledge Agent **v2**.

Run it:

    # One-shot, offline, with the dev trace and local tools (no MCP servers):
    TECHCORP_OFFLINE=true uv run python -m techcorp_agent.capstone_v2.cli \
        --question "What is 17.5% of 8,400?" --dev --no-mcp

    # Interactive REPL (Ctrl-D / 'exit' to quit) — a durable multi-turn thread:
    uv run python -m techcorp_agent.capstone_v2.cli

    # Stream the node-by-node event feed as the agent works:
    uv run python -m techcorp_agent.capstone_v2.cli -q "How much vacation do I get?" --stream

Two display modes:

- **user mode** (default) hides internals — only the answer and its sources;
- **dev mode** (``--dev``) additionally prints the LangGraph ``trace`` and route.

v2 upgrades over the v1 CLI:

- **Durable memory (Module 15).** The conversation is checkpointed to SQLite, so
  a follow-up resolves against earlier turns and the thread survives a restart.
  Pass ``--conversation-id`` to resume an existing thread.
- **Approval gate (Module 16).** A "create a support ticket" request pauses for a
  human decision; the REPL prompts ``approve? [y/N]`` and resumes accordingly.
- **Streaming (Module 16).** ``--stream`` prints the normalized ``AgentEvent``
  feed (which node ran, which route was chosen) as the graph executes.

MCP: by default the CLI spawns the calculator + orders MCP servers (Modules
13-14). ``--no-mcp`` uses the in-process local tools instead; the CLI also
auto-falls back to local tools if spawning fails, so a broken MCP setup never
blocks the agent.
"""

from __future__ import annotations

import argparse
import tempfile
import uuid
from pathlib import Path
from typing import Any

from langgraph.types import Command

from techcorp_agent.capstone.mcp_bridge import SyncMCPRegistry
from techcorp_agent.capstone_v2 import build_v2_graph, build_v2_store
from techcorp_agent.config import get_settings
from techcorp_agent.llm.factory import get_llm_client
from techcorp_agent.streaming.events import INTERRUPT_KEY, stream_agent_events


def _memory_db_path() -> Path:
    """Where the CLI checkpoints conversations (durable across restarts)."""
    return Path(tempfile.gettempdir()) / "techcorp_v2_cli_memory.sqlite3"


def _print_result(state: dict, dev: bool) -> None:
    print(f"\nAgent: {state.get('answer', '').strip()}")
    sources = state.get("sources") or []
    if sources:
        print(f"Sources: {', '.join(sources)}")
    if dev:
        print("\n[dev] trace:")
        for line in state.get("trace", []):
            print(f"  {line}")
        print(f"[dev] route: {state.get('route')}")


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in {"y", "yes", "approve"}
    except EOFError:
        return False


def _run_turn(app: Any, question: str, config: dict, *, stream: bool, dev: bool) -> dict:
    """Run one turn; handle a possible approval interrupt and streaming."""
    if stream:
        for ev in stream_agent_events(app, {"question": question, "trace": []}, config):
            print(f"  · {ev.summary}")
        snapshot = app.get_state(config)
        state = snapshot.values if snapshot else {}
    else:
        state = app.invoke({"question": question, "trace": []}, config)

    # Approval gate (Module 16): the ticket node interrupts before the write.
    if isinstance(state, dict) and INTERRUPT_KEY in state:
        interrupts = state[INTERRUPT_KEY]
        first = interrupts[0] if isinstance(interrupts, (list, tuple)) else interrupts
        payload = getattr(first, "value", first)
        print("\n[approval required] The agent wants to perform a write action:")
        if isinstance(payload, dict):
            print(f"  action:  {payload.get('action')}")
            print(f"  summary: {payload.get('summary')}")
            if payload.get("order_id"):
                print(f"  order:   {payload.get('order_id')}")
        approved = _confirm("approve? [y/N] ")
        state = app.invoke(Command(resume="approve" if approved else "reject"), config)
    return state


def run(
    question: str | None,
    *,
    dev: bool = False,
    conversation_id: str | None = None,
    use_mcp: bool = True,
    stream: bool = False,
) -> int:
    """Drive the agent once (``question`` given) or as a REPL (``question`` None)."""
    settings = get_settings()
    llm = get_llm_client(settings)
    store = build_v2_store()

    registry = SyncMCPRegistry.connect() if use_mcp else None
    if use_mcp and registry is None:
        print("[info] MCP servers unavailable — using local calculator/order tools.")

    conversation_id = conversation_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": conversation_id}}

    print(f"TechCorp Knowledge Agent v2  (conversation {conversation_id})")
    print(f"mode: {'dev' if dev else 'user'} | mcp: {'on' if registry else 'off (local tools)'}")

    try:
        app = build_v2_graph(llm, store, mcp_registry=registry, db_path=_memory_db_path())

        if question is not None:
            state = _run_turn(app, question, config, stream=stream, dev=dev)
            _print_result(state, dev)
            return 0

        print("Type a question, or 'exit' / Ctrl-D to quit.\n")
        turns = 0
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
            state = _run_turn(app, line, config, stream=stream, dev=dev)
            _print_result(state, dev)
            turns += 1
            print()
        print(f"\nConversation {conversation_id} had {turns} turn(s). Goodbye.")
        return 0
    finally:
        if registry is not None:
            registry.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="techcorp-capstone-v2",
        description="TechCorp Knowledge Agent v2 — the integrated hero-capstone agent.",
    )
    parser.add_argument(
        "--question", "-q", help="Ask one question and exit. Omit for an interactive REPL."
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Developer mode: print the trace + route after each turn.",
    )
    parser.add_argument(
        "--user",
        action="store_true",
        help="User mode (default): hide all internals. Overrides --dev if both are given.",
    )
    parser.add_argument(
        "--conversation-id",
        help="Resume a durable conversation thread (a uuid4 is minted if omitted).",
    )
    parser.add_argument(
        "--no-mcp", action="store_true", help="Skip MCP servers; use the in-process local tools."
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream the node-by-node event feed as the agent works.",
    )
    args = parser.parse_args(argv)
    dev = args.dev and not args.user
    return run(
        args.question,
        dev=dev,
        conversation_id=args.conversation_id,
        use_mcp=not args.no_mcp,
        stream=args.stream,
    )


if __name__ == "__main__":
    raise SystemExit(main())
