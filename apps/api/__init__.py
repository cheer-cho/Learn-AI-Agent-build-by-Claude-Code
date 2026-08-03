"""TechCorp Knowledge Agent — the production HTTP service (Module 21).

``apps.api.main:app`` is a FastAPI application that serves the memory-enabled
capstone agent over HTTP. It loads the vector index and builds the agent graph
**once** at startup (a lifespan handler), applies safety validation and a
per-session budget at the boundary, and exposes ``/chat``, ``/chat/stream``,
``/health``, and ``/ready``.

Run it (offline, no Docker required)::

    uv run uvicorn apps.api.main:app
"""

from apps.api.main import app

__all__ = ["app"]
