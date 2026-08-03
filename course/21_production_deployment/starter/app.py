"""Module 21 starter — complete the production app wiring.

Complete each marked block below to build a FastAPI service that serves the
memory-enabled capstone agent. The reference implementation is ``apps/api/main.py``
— read it, but do the wiring yourself here. The shared library gives you the
graph, the memory checkpointer, and the safety helpers; your job is the
*envelope*: a lifespan handler that loads the agent once, plus the four endpoints.

Each block to complete is marked with an inline comment starting ``# T`` ``ODO:``.
Once every one of those markers is gone, ``tests/test_my_work.py`` un-skips and
becomes your gate:

    uv run pytest course/21_production_deployment -q

Run it directly, offline, with no server:

    uv run uvicorn course.21_production_deployment.starter.app:app
"""

from __future__ import annotations

import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# The safety helpers live with the production app; reuse them here.
from apps.api.safety import SessionBudget, validate_input, validate_output
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from techcorp_agent.capstone import build_offline_store
from techcorp_agent.config import get_settings
from techcorp_agent.llm.factory import get_llm_client
from techcorp_agent.memory.checkpointing import build_memory_graph


class ChatRequest(BaseModel):
    """The POST /chat body. ``question`` is required (a missing one is a 422)."""

    question: str = Field(..., description="The user's question.")
    conversation_id: str | None = Field(default=None)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    conversation_id: str
    route: str | None = None


def _memory_db_path() -> Path:
    """Where the conversation checkpointer persists (override with TECHCORP_MEMORY_DB)."""
    override = os.environ.get("TECHCORP_MEMORY_DB")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "techcorp_api_memory_starter.sqlite3"


def build_agent() -> Any:
    """Build the index + the memory-enabled agent graph. Called ONCE at startup."""
    # TODO: build and return the agent graph:
    #   settings = get_settings()
    #   llm = get_llm_client(settings)
    #   store = build_offline_store()
    #   return build_memory_graph(llm, store, _memory_db_path())
    raise NotImplementedError("build the agent graph")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown. Build the agent ONCE here, not per request."""
    # TODO: in the startup section (before ``yield``) set:
    #   app.state.agent = build_agent()
    #   app.state.budget = SessionBudget()
    #   app.state.ready = True
    # then ``yield``; in the shutdown section (after ``yield``) set
    #   app.state.ready = False
    yield


app = FastAPI(title="TechCorp Knowledge Agent API (starter)", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    """Liveness: is the process up? Cheap and dependency-free."""
    # TODO: return {"status": "ok"}
    return {}


@app.get("/ready")
def ready(request: Request) -> JSONResponse:
    """Readiness: 200 once the index is loaded, else 503."""
    # TODO: is_ready = bool(getattr(request.app.state, "ready", False))
    #       return JSONResponse(
    #           {"ready": is_ready}, status_code=200 if is_ready else 503
    #       )
    is_ready = False
    return JSONResponse({"ready": is_ready}, status_code=503)


@app.post("/chat", response_model=ChatResponse)
def chat(request: Request, body: ChatRequest) -> JSONResponse:
    """Answer one question with safety validation + a per-session budget."""
    # TODO: implement the flow:
    #   1. conversation_id = body.conversation_id or uuid.uuid4().hex
    #   2. check = validate_input(body.question)
    #      if not check.ok:
    #          return JSONResponse({"error": check.reason}, status_code=400)
    #   3. budget = request.app.state.budget
    #      bc = budget.check_and_consume(conversation_id)
    #      if not bc.ok:
    #          return JSONResponse({"error": bc.reason}, status_code=429)
    #   4. config = {"configurable": {"thread_id": conversation_id}}
    #      state = request.app.state.agent.invoke(
    #          {"question": body.question, "trace": []}, config=config
    #      )
    #   5. answer = validate_output(state.get("answer"))
    #      return JSONResponse(ChatResponse(
    #          answer=answer, sources=state.get("sources") or [],
    #          conversation_id=conversation_id, route=state.get("route"),
    #      ).model_dump())
    return JSONResponse({"error": "not implemented"}, status_code=500)


# NOTE: the streaming endpoint (/chat/stream) is intentionally left to the
# production app (apps/api/main.py); focus your starter work on the four
# endpoints above. Study apps/api/main.py to see how SSE is wired.
