"""The v2 FastAPI service — production HTTP for the integrated agent (Modules 21 + 22).

Module 21 turned the *memory* graph into a service (``apps/api/main.py``). v2 does
the same for the *integrated* graph, reusing Module 21's exact patterns and
reimplementing none of them:

- **Load once, not per request.** The index and the compiled v2 graph are built a
  single time in a **lifespan handler** and stashed on ``app.state``; every
  request reuses them. Rebuilding per call would melt under load.
- **Health vs readiness.** ``/health`` is a cheap liveness probe; ``/ready`` is
  ``200`` only once the graph is built (readiness). Orchestrators restart on
  liveness failure and pull-from-LB on readiness failure.
- **Streaming over HTTP** via Server-Sent Events, reusing
  ``techcorp_agent.streaming.stream_agent_events`` — the same normalizer the CLI
  uses, delivered as ``text/event-stream``.
- **Safety at the edge** *and* in the graph. The v2 graph already validates input,
  scans for injection, and enforces a budget at its ``boundary`` node, so this
  layer is thin: it maps HTTP requests onto the graph and formats the responses.
- **Structured logging without secrets** — request *metadata* (id, route,
  latencies, lengths), never the raw question, the answer, or any key.

Why a separate module (not an edit to ``apps/api``): the assignment forbids
breaking the existing service or its tests. ``build_v2_app()`` returns an
independent FastAPI app you can mount or run on its own::

    uv run uvicorn techcorp_agent.capstone_v2.app_service:app --reload

Endpoint map (mirrors Module 21, so a client written for v1 works against v2):

- ``GET  /health``      — liveness, always 200.
- ``GET  /ready``       — readiness, 200 once the graph is warm else 503.
- ``POST /chat``        — one turn; ``{question, conversation_id?}`` ->
  ``{answer, sources, conversation_id, route}``. The graph's own boundary returns
  a safe answer for blocked input (still a 200 with a clear message).
- ``POST /chat/stream`` — the same turn as SSE ``node``/``route``/``answer`` frames.

Everything runs against the deterministic mock LLM offline with no API key.
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

from techcorp_agent.capstone_v2 import build_v2_graph, build_v2_store
from techcorp_agent.config import get_settings
from techcorp_agent.llm.factory import get_llm_client

logger = logging.getLogger("techcorp.api.v2")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


def log_event(event: str, **fields: Any) -> None:
    """Emit one structured, secrets-free log line (metadata only)."""
    logger.info(json.dumps({"event": event, **fields}, sort_keys=True))


class ChatRequest(BaseModel):
    question: str = Field(..., description="The user's question.")
    conversation_id: str | None = Field(
        default=None,
        description="Reuse to continue a conversation; a new id is minted when omitted.",
    )


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    conversation_id: str
    route: str | None = None


def _memory_db_path() -> Path:
    """Where the v2 service checkpoints conversations (overridable for a volume)."""
    override = os.environ.get("TECHCORP_V2_MEMORY_DB")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "techcorp_v2_api_memory.sqlite3"


def build_agent() -> Any:
    """Build the index + the integrated v2 graph. Called once at startup."""
    settings = get_settings()
    llm = get_llm_client(settings)
    store = build_v2_store()
    return build_v2_graph(llm, store, db_path=_memory_db_path())


def build_v2_app() -> FastAPI:
    """Construct the v2 FastAPI application (its own app, independent of apps/api)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        t0 = time.perf_counter()
        log_event("startup.begin")
        app.state.agent = build_agent()
        app.state.ready = True
        log_event("startup.ready", elapsed_ms=round((time.perf_counter() - t0) * 1000, 1))
        try:
            yield
        finally:
            app.state.ready = False
            log_event("shutdown")

    app = FastAPI(
        title="TechCorp Knowledge Agent v2 API",
        version="2.0.0",
        summary="Production HTTP service for the integrated TechCorp Knowledge Agent (Module 22).",
        lifespan=lifespan,
    )

    def _agent(request: Request) -> Any:
        return request.app.state.agent

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready", tags=["ops"])
    def ready(request: Request) -> JSONResponse:
        is_ready = bool(getattr(request.app.state, "ready", False))
        return JSONResponse({"ready": is_ready}, status_code=200 if is_ready else 503)

    @app.post("/chat", response_model=ChatResponse, tags=["chat"])
    def chat(request: Request, body: ChatRequest) -> JSONResponse:
        request_id = uuid.uuid4().hex[:12]
        conversation_id = body.conversation_id or uuid.uuid4().hex
        t0 = time.perf_counter()
        config = {"configurable": {"thread_id": conversation_id}}

        # The v2 graph applies input validation / injection / budget at its
        # boundary node, so a blocked turn returns a safe answer here (a 200 with
        # a clear message), matching the graceful-degradation contract.
        state = _agent(request).invoke({"question": body.question, "trace": []}, config)
        answer = state.get("answer") or "I couldn't produce an answer for that."
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
                answer=answer, sources=sources, conversation_id=conversation_id, route=route
            ).model_dump()
        )

    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    @app.post("/chat/stream", tags=["chat"])
    def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
        from techcorp_agent.streaming import stream_agent_events

        request_id = uuid.uuid4().hex[:12]
        conversation_id = body.conversation_id or uuid.uuid4().hex
        agent = _agent(request)

        def event_stream() -> Iterator[str]:
            yield _sse("start", {"conversation_id": conversation_id})
            config = {"configurable": {"thread_id": conversation_id}}
            try:
                for ev in stream_agent_events(
                    agent, {"question": body.question, "trace": []}, config
                ):
                    yield _sse(ev.type, {"node": ev.node, "summary": ev.summary})
            except Exception as exc:  # noqa: BLE001 - a mid-stream failure is data, not a 500
                log_event("stream.error", request_id=request_id, error=type(exc).__name__)
                yield _sse("error", {"error": "the agent failed to complete this turn"})
                return
            snapshot = agent.get_state(config)
            final = snapshot.values if snapshot else {}
            answer = final.get("answer") or "I couldn't produce an answer for that."
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

    return app


# A module-level app so ``uvicorn techcorp_agent.capstone_v2.app_service:app`` works.
app = build_v2_app()
