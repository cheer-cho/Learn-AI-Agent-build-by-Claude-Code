"""TechCorp Knowledge Agent — the production FastAPI service (Module 21).

This is the "Act 3" deliverable: IT will not run a script, they will run a
*service* — one that starts with a documented command, answers over HTTP,
streams, and reports whether it is healthy and ready. This module turns the
memory-enabled capstone agent into exactly that, and reimplements none of the
agent: it *composes* the library the earlier modules built.

The teaching points, made concrete here:

- **Load once, not per request.** The vector index and the compiled agent graph
  are expensive to build. A naive service rebuilds them on every call and melts
  under load. We build them exactly once in a **lifespan handler**
  (:func:`lifespan`) and stash them on ``app.state``; every request reuses them.
- **Health vs readiness.** ``/health`` answers "is the process alive?" (liveness)
  and is cheap and dependency-free. ``/ready`` answers "can it actually serve?"
  (readiness) — it is ``200`` only once the index is loaded. Orchestrators treat
  these differently: liveness failures restart the pod, readiness failures just
  pull it out of the load-balancer until it warms up.
- **Streaming over HTTP** via Server-Sent Events, reusing
  ``techcorp_agent.streaming`` — the same event/token stream the CLI uses, now
  delivered as ``text/event-stream`` chunks.
- **Safety at the edge.** Input validation, a per-session budget, and an
  output check are applied here (see :mod:`apps.api.safety`), because the HTTP
  boundary is where untrusted input arrives.
- **Structured logging without secrets.** We log request *metadata* — a request
  id, the route, latencies, lengths — never the raw question, the answer, or any
  key. (Module 20's PII lesson, applied to logs.)

Run it — offline, no Docker needed::

    uv run uvicorn apps.api.main:app --reload

Everything runs against the deterministic mock LLM with no API key: the graph is
built with ``get_llm_client``, which returns the mock whenever the app is
offline (the default).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from apps.api.safety import (
    SessionBudget,
    validate_input,
    validate_output,
)
from techcorp_agent.capstone import build_offline_store
from techcorp_agent.config import get_settings
from techcorp_agent.llm.factory import get_llm_client
from techcorp_agent.memory.checkpointing import build_memory_graph

# -- structured logging (metadata only, never content or secrets) -------------

logger = logging.getLogger("techcorp.api")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


def log_event(event: str, **fields: Any) -> None:
    """Emit one structured, secrets-free log line.

    We log *facts about* a request — its id, route, timing, and the *lengths* of
    the question and answer — but never the question text, the answer text, or
    any credential. That is the whole discipline: a log you can safely ship to a
    central store must not carry user content or secrets (Module 20's PII rule
    applied to observability).
    """
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, sort_keys=True))


# -- request / response models -------------------------------------------------


class ChatRequest(BaseModel):
    """The ``POST /chat`` body. ``question`` is required; the rest are optional.

    A missing or non-string ``question`` fails Pydantic validation and FastAPI
    returns ``422`` automatically — a clear error, not a crash (a Module 21 lab
    assertion).
    """

    question: str = Field(..., description="The user's question.")
    conversation_id: str | None = Field(
        default=None,
        description="Reuse to continue a conversation; a new id is minted when omitted.",
    )


class ChatResponse(BaseModel):
    """The ``POST /chat`` reply: the grounded answer, its sources, and the thread id."""

    answer: str
    sources: list[str] = Field(default_factory=list)
    conversation_id: str
    route: str | None = None


# -- the agent, built once at startup -----------------------------------------


def _memory_db_path() -> Path:
    """Where the conversation checkpointer persists.

    Defaults to a file under the system temp dir so the service is runnable with
    zero setup and offline; a real deployment overrides it with
    ``TECHCORP_MEMORY_DB`` (e.g. a path on a mounted volume) so conversations
    survive restarts.
    """
    override = os.environ.get("TECHCORP_MEMORY_DB")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "techcorp_api_memory.sqlite3"


def build_agent() -> Any:
    """Build the index + the memory-enabled agent graph. Called once at startup.

    This is the expensive work the lifespan handler does a single time: index the
    corpus into the offline vector store and compile the checkpointed capstone
    graph. The returned graph is reused by every request — never rebuilt per call.
    """
    settings = get_settings()
    llm = get_llm_client(settings)
    store = build_offline_store()
    db_path = _memory_db_path()
    graph = build_memory_graph(llm, store, db_path)
    return graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: load the index + graph once, expose them on ``app.state``.

    The body before ``yield`` runs once when the process starts; the code after
    it runs at shutdown. We build the agent here (not at import time and not per
    request) so a single warm graph serves the whole process lifetime. Until this
    finishes, ``/ready`` reports not-ready — which is exactly what a load balancer
    should see while the service warms up.
    """
    t0 = time.perf_counter()
    log_event("startup.begin")
    app.state.agent = build_agent()
    app.state.budget = SessionBudget()
    app.state.ready = True
    log_event("startup.ready", elapsed_ms=round((time.perf_counter() - t0) * 1000, 1))
    try:
        yield
    finally:
        app.state.ready = False
        log_event("shutdown")


app = FastAPI(
    title="TechCorp Knowledge Agent API",
    version="1.0.0",
    summary="Production HTTP service for the TechCorp Knowledge Agent (Module 21).",
    lifespan=lifespan,
)


# -- helpers -------------------------------------------------------------------


def _agent(request: Request) -> Any:
    """The single warm agent graph built at startup."""
    return request.app.state.agent


def _budget(request: Request) -> SessionBudget:
    return request.app.state.budget


def _run_turn(agent: Any, question: str, conversation_id: str) -> dict:
    """Invoke the memory graph for one turn on ``conversation_id``.

    The checkpointer threads history by ``thread_id``: passing the same
    ``conversation_id`` again continues the conversation — the prior turns are
    reloaded from SQLite and prepended to the prompt automatically. The graph's
    own graceful degradation means a down MCP server or an unknown order comes
    back as a clean answer, so this call does not raise on those paths.
    """
    config = {"configurable": {"thread_id": conversation_id}}
    return agent.invoke({"question": question, "trace": []}, config=config)


# -- endpoints -----------------------------------------------------------------


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness: is the process up? Cheap, dependency-free, always ``200`` here.

    A container orchestrator hits this to decide whether to *restart* the pod.
    It must not touch the index or the model — otherwise a slow dependency looks
    like a dead process and triggers a needless restart.
    """
    return {"status": "ok"}


@app.get("/ready", tags=["ops"])
def ready(request: Request) -> JSONResponse:
    """Readiness: can the service actually serve? ``200`` only once the index loaded.

    Returns ``503`` until the lifespan handler has finished building the agent.
    Orchestrators use this to decide whether to route traffic here — a not-ready
    instance is pulled from the load balancer without being killed.
    """
    is_ready = bool(getattr(request.app.state, "ready", False))
    status_code = 200 if is_ready else 503
    return JSONResponse({"ready": is_ready}, status_code=status_code)


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: Request, body: ChatRequest) -> JSONResponse:
    """Answer one question, applying safety validation and a per-session budget.

    Flow: validate input -> check the session budget -> run one agent turn ->
    validate output -> reply with the answer, its sources, and the conversation
    id. A bad question is a clean ``400``; an over-budget session is a ``429``;
    an unknown order or a down tool is still a ``200`` with a safe message,
    because the agent degrades rather than raising.
    """
    request_id = uuid.uuid4().hex[:12]
    conversation_id = body.conversation_id or uuid.uuid4().hex
    t0 = time.perf_counter()

    check = validate_input(body.question)
    if not check.ok:
        log_event("chat.rejected", request_id=request_id, reason=check.reason)
        return JSONResponse({"error": check.reason}, status_code=400)

    budget_check = _budget(request).check_and_consume(conversation_id)
    if not budget_check.ok:
        log_event("chat.over_budget", request_id=request_id, reason=budget_check.reason)
        return JSONResponse({"error": budget_check.reason}, status_code=429)

    state = _run_turn(_agent(request), body.question, conversation_id)
    answer = validate_output(state.get("answer"))
    sources = state.get("sources") or []
    route = state.get("route")

    log_event(
        "chat.answered",
        request_id=request_id,
        route=route,
        question_chars=len(body.question),
        answer_chars=len(answer),
        source_count=len(sources),
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
    )
    return JSONResponse(
        ChatResponse(
            answer=answer,
            sources=sources,
            conversation_id=conversation_id,
            route=route,
        ).model_dump()
    )


def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event frame.

    The SSE wire format is line-oriented: an optional ``event:`` name, a
    ``data:`` payload (we JSON-encode ours), and a blank line to terminate the
    frame. Any HTTP client — including ``curl -N`` — can read this incrementally.
    """
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/chat/stream", tags=["chat"])
def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """Stream the answer as Server-Sent Events.

    Reuses ``techcorp_agent.streaming.stream_agent_events`` — the *same* event
    normalizer the CLI uses — to emit one ``node``/``route`` SSE frame per graph
    super-step as the agent works, then a final ``answer`` frame carrying the
    grounded answer, its sources, and the conversation id. Safety checks run
    first; a rejection is streamed as a single ``error`` frame (the response has
    already committed to ``text/event-stream``, so we signal the error in-band).
    """
    from techcorp_agent.streaming import stream_agent_events

    request_id = uuid.uuid4().hex[:12]
    conversation_id = body.conversation_id or uuid.uuid4().hex
    agent = _agent(request)
    budget = _budget(request)

    def event_stream() -> Iterator[str]:
        check = validate_input(body.question)
        if not check.ok:
            log_event("stream.rejected", request_id=request_id, reason=check.reason)
            yield _sse("error", {"error": check.reason})
            return
        budget_check = budget.check_and_consume(conversation_id)
        if not budget_check.ok:
            log_event("stream.over_budget", request_id=request_id, reason=budget_check.reason)
            yield _sse("error", {"error": budget_check.reason})
            return

        yield _sse("start", {"conversation_id": conversation_id})
        config = {"configurable": {"thread_id": conversation_id}}
        final: dict[str, Any] = {}
        try:
            for ev in stream_agent_events(agent, {"question": body.question, "trace": []}, config):
                yield _sse(ev.type, {"node": ev.node, "summary": ev.summary})
        except Exception as exc:  # noqa: BLE001 - a mid-stream failure is data, not a 500
            log_event("stream.error", request_id=request_id, error=type(exc).__name__)
            yield _sse("error", {"error": "the agent failed to complete this turn"})
            return

        # Read the final, checkpointed state for the grounded answer + sources.
        snapshot = agent.get_state(config)
        final = snapshot.values if snapshot else {}
        answer = validate_output(final.get("answer"))
        sources = final.get("sources") or []
        log_event(
            "stream.answered",
            request_id=request_id,
            route=final.get("route"),
            answer_chars=len(answer),
            source_count=len(sources),
        )
        yield _sse(
            "answer",
            {
                "answer": answer,
                "sources": sources,
                "conversation_id": conversation_id,
                "route": final.get("route"),
            },
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/metrics", tags=["ops"])
def metrics(request: Request) -> dict:
    """A tiny liveness-adjacent counters endpoint (the lab's stretch goal).

    Not Prometheus — just enough to show where a real ``/metrics`` would live:
    how many distinct conversations the process has seen and their total turns.
    """
    budget: SessionBudget = request.app.state.budget
    counts = budget._counts  # noqa: SLF001 - reading our own in-process counter
    return {
        "conversations": len(counts),
        "total_turns": sum(counts.values()),
    }
