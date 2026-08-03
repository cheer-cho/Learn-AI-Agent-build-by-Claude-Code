"""Module 21 solution — the production app.

There is nothing new to implement here: the reference service *is* the production
service at ``apps/api/main.py``. The whole point of this module is that the thing
you deploy and the thing you complete in ``starter/app.py`` are the same
application, so this file simply re-exports it. Read ``apps/api/main.py`` for the
fully-commented implementation.

    uv run uvicorn apps.api.main:app          # deploy the real service
    uv run python course/21_production_deployment/solution/smoke.py   # offline smoke
"""

from __future__ import annotations

from apps.api.main import (
    ChatRequest,
    ChatResponse,
    app,
    build_agent,
    lifespan,
)

__all__ = ["ChatRequest", "ChatResponse", "app", "build_agent", "lifespan"]
