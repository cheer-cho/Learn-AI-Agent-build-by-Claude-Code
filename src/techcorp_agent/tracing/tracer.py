"""The local, offline-first tracer for the TechCorp agent (Module 19).

Observability without a SaaS account. Leadership's Act-3 question — "what is the
agent doing, and did that change make it better or worse?" — needs a *record* of
every run, not a vibe. LangSmith is the recommended live path (see
``langsmith_bridge``), but nothing here requires a key or a network: every run is
appended as one JSON line to ``artifacts/traces/runs.jsonl`` and rendered by
``scripts/view_traces.py``.

The vocabulary maps 1:1 onto LangSmith's:

- a **run** is one top-level invocation (LangSmith: a root run) — here a
  :class:`Run` opened by ``LocalTracer.run(...)``;
- a **step** is one unit of work inside a run (LangSmith: a child run / span) —
  here an entry appended by :meth:`Run.log_step`;
- **token usage** and **latency** are per-run metrics (LangSmith run metadata),
  set by :meth:`Run.set_metrics`.

Design choices that carry their weight:

- **One JSON line per run.** JSONL is append-only, greppable, and never needs a
  parser to read a single record — exactly what a trace log wants.
- **The line is always written**, even when the run body raises: the exception
  is captured into the ``error`` field and re-raised, so a crash is *data*, not a
  gap in the record (the same "a failure is data" stance the capstone nodes take).
- **Thread-safe append.** A module-level lock serialises the write so concurrent
  runs can't interleave half-lines in the file.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# One lock guards every append to any traces file in this process. Appends are
# short (a single ``write`` of one line), so a single global lock is simpler than
# a per-path registry and cannot deadlock.
_WRITE_LOCK = threading.Lock()

DEFAULT_TRACE_PATH = Path("artifacts/traces/runs.jsonl")


class Run:
    """A single in-progress run. Obtained from :meth:`LocalTracer.run`.

    A run accumulates ``steps`` (via :meth:`log_step`), an ``output`` (via
    :meth:`set_output`), and per-run metrics (via :meth:`set_metrics`). The
    tracer writes it to disk exactly once, when the ``with`` block exits.
    """

    def __init__(self, name: str, inputs: dict[str, Any] | None):
        self.run_id: str = str(uuid.uuid4())
        self.name: str = name
        self.inputs: dict[str, Any] = dict(inputs or {})
        self.steps: list[dict[str, Any]] = []
        self.output: Any = None
        self.token_usage: dict[str, int] = {}
        self.latency_ms: float | None = None
        self.error: str | None = None

    def log_step(self, node: str, data: Any = None) -> None:
        """Record one step (a node visited, a tool called) in visit order.

        ``node`` is the step name; ``data`` is any JSON-serialisable detail
        (the router's decision, a tool result, a chunk count). Steps are kept in
        the order they were logged — that order *is* the execution path.
        """
        self.steps.append({"node": node, "data": data})

    def set_output(self, output: Any) -> None:
        """Set the run's final output (the agent's answer, typically)."""
        self.output = output

    def set_metrics(
        self,
        tokens: dict[str, int] | int | None = None,
        latency_ms: float | None = None,
    ) -> None:
        """Attach per-run cost/latency metrics.

        ``tokens`` may be a ``{"input_tokens", "output_tokens", "total_tokens"}``
        dict or a single int (treated as the total); ``latency_ms`` overrides the
        wall-clock latency the tracer measures automatically.
        """
        if isinstance(tokens, int):
            self.token_usage = {"total_tokens": tokens}
        elif tokens is not None:
            self.token_usage = dict(tokens)
        if latency_ms is not None:
            self.latency_ms = latency_ms

    def to_record(self) -> dict[str, Any]:
        """The JSON record persisted for this run (one JSONL line)."""
        return {
            "run_id": self.run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "name": self.name,
            "inputs": self.inputs,
            "steps": self.steps,
            "output": self.output,
            "token_usage": self.token_usage,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


class LocalTracer:
    """Writes one JSON line per run to a JSONL trace log.

    Usage as a context manager::

        tracer = LocalTracer(path)
        with tracer.run("agent", {"question": q}) as run:
            run.log_step("router", {"route": "retrieval"})
            run.set_output(answer)
            run.set_metrics(tokens={"total_tokens": 512}, latency_ms=12.3)

    or as a decorator::

        @tracer.trace("nightly-eval")
        def pipeline(example): ...

    The record is written when the ``with`` block exits — including when the body
    raises, in which case the exception text lands in the ``error`` field and the
    exception propagates (the run is *recorded as failed*, not swallowed).
    """

    def __init__(
        self,
        path: Path | str = DEFAULT_TRACE_PATH,
        *,
        bridge: Any | None = None,
    ):
        self.path = Path(path)
        # An optional LangSmith mirror. ``None`` (the default) keeps the tracer
        # entirely local; a disabled bridge no-ops, so nothing here needs a key.
        self._bridge = bridge

    @contextmanager
    def run(self, name: str, inputs: dict[str, Any] | None = None) -> Iterator[Run]:
        """Open a run as a context manager; write it on exit (even on error)."""
        run = Run(name, inputs)
        start = time.perf_counter()
        try:
            yield run
        except Exception as exc:  # noqa: BLE001 - record the failure, then re-raise
            run.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if run.latency_ms is None:
                run.latency_ms = round((time.perf_counter() - start) * 1000, 3)
            self._write(run)

    def trace(self, name: str | None = None):
        """Decorator form: wrap a function so each call is one traced run.

        The wrapped function receives the open :class:`Run` as a keyword argument
        ``run`` when it declares that parameter; otherwise it is called normally
        and only its return value is recorded as the output.
        """

        def decorator(func):
            run_name = name or func.__name__

            def wrapper(*args, **kwargs):
                import inspect

                with self.run(run_name, {"args": _safe(args), "kwargs": _safe(kwargs)}) as run:
                    if "run" in inspect.signature(func).parameters:
                        result = func(*args, run=run, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    if run.output is None:
                        run.set_output(_safe(result))
                    return result

            return wrapper

        return decorator

    def _write(self, run: Run) -> None:
        """Append the run as one JSON line; mirror to LangSmith if a bridge is on."""
        record = run.to_record()
        line = json.dumps(record, default=_safe, ensure_ascii=False)
        with _WRITE_LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        # Mirroring is best-effort and never blocks or breaks the local write.
        if self._bridge is not None:
            try:
                self._bridge.mirror(record)
            except Exception:  # noqa: BLE001 - a bridge failure must not lose the local trace
                pass


def _safe(value: Any) -> Any:
    """Best-effort coercion of arbitrary values into JSON-friendly forms."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    # Pydantic models (ChatResult, RAGAnswer, ...) know how to dump themselves.
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return _safe(dump())
        except Exception:  # noqa: BLE001
            pass
    return str(value)


# -- trace_agent: capture a capstone-graph invocation automatically ----------

# The capstone graph writes trace lines shaped ``[node=NAME] detail`` into
# ``state["trace"]`` (see ``capstone/state.py``). We parse that back out so the
# tracer records the same nodes/route the graph actually visited — no need to
# instrument the shared graph code itself.
_NODE_RE = None


def _parse_trace_line(line: str) -> dict[str, Any]:
    """Turn a ``[node=router] tool=x route=y`` trace line into a step dict."""
    import re

    global _NODE_RE
    if _NODE_RE is None:
        _NODE_RE = re.compile(r"^\[node=(?P<node>[^\]]+)\]\s*(?P<detail>.*)$")
    match = _NODE_RE.match(line)
    if not match:
        return {"node": "unknown", "data": line}
    return {"node": match.group("node"), "data": match.group("detail") or None}


def trace_agent(
    graph: Any,
    question: str,
    tracer: LocalTracer,
    config: dict[str, Any] | None = None,
    *,
    name: str = "techcorp-agent",
    llm: Any | None = None,
) -> dict[str, Any]:
    """Invoke a capstone-style ``graph`` on ``question`` and record the run.

    Records, automatically from the result state:

    - each node visited and its detail, in order (from ``state["trace"]``);
    - the chosen route (as an extra step and in the run output);
    - the final answer and cited sources (the run output);
    - token usage — from the mock/real LLM's ``.calls``/usage when an ``llm`` is
      passed (the mock client records every call), else omitted;
    - latency — wall-clock around ``graph.invoke``.

    Returns the final graph state unchanged, so callers can assert on it.
    """
    initial = {
        "conversation_id": (config or {}).get("conversation_id", "trace"),
        "question": question,
        "trace": [],
        "loop_count": 0,
    }
    with tracer.run(name, {"question": question}) as run:
        state = graph.invoke(initial)

        for line in state.get("trace", []):
            step = _parse_trace_line(line)
            run.log_step(step["node"], step["data"])

        route = state.get("route")
        if route is not None:
            run.log_step("route", route)

        run.set_output(
            {
                "route": route,
                "answer": state.get("answer", ""),
                "sources": state.get("sources", []),
            }
        )
        run.set_metrics(tokens=_tokens_from_llm(llm))
    return state


def _tokens_from_llm(llm: Any | None) -> dict[str, int]:
    """Sum token usage from a mock/real client's recorded calls, if available.

    The offline ``MockLLMClient`` records every prompt in ``.calls`` but not the
    per-call usage, so we approximate total tokens from the prompt text the same
    way the mock does (~4 chars/token). A real client exposes usage on each
    result; when neither is available we simply omit the metric rather than lie.
    """
    if llm is None:
        return {}
    calls = getattr(llm, "calls", None)
    if not calls:
        return {}
    approx = 0
    for messages in calls:
        approx += sum(max(1, len(m.content) // 4) for m in messages)
    return {"input_tokens": approx, "output_tokens": 0, "total_tokens": approx}
