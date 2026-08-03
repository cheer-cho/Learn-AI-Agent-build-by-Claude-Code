[🗺 Course Roadmap](../../ROADMAP.html) · [← 20 Guardrails & Safety](../20_guardrails_and_safety/README.md) · [22 Hero Capstone →](../22_hero_capstone/README.md)

# Module 21 — Production Deployment

## Objective

Cross the line from *script* to *service*. Act 3 of the TechCorp story has IT
refusing to run a Python file by hand — they want a deployable, monitored HTTP
service they can start with one command, watch for health, and put behind a load
balancer. In this module you wrap the memory-enabled capstone agent in a FastAPI
application that loads its index **once** at startup, streams answers over Server-
Sent Events, reports liveness and readiness, applies safety validation and a
budget at the boundary, logs without leaking secrets, and ships with a Dockerfile,
a Compose file, and a CI workflow. Everything runs **offline** and **without
Docker** — Docker is an optional path, not a requirement.

## Difficulty

Advanced

## Prerequisites

- Module 14 (the capstone agent graph you are serving)
- Module 15 (the SQLite checkpointer — conversation threads by `conversation_id`)
- Module 16 (the streaming event/token stream you deliver as SSE)
- Module 20 (guardrails: input/output validation, budget, PII-safe logging)
- No API key required — the service boots against the deterministic mock LLM.

## What you will build / study

The production service already lives in `apps/api/main.py` (read it — it is the
reference). In this module you:

1. **Run** it with Uvicorn and hit `/health`, `/ready`, and `/chat` with curl.
2. **Stream** a response from `/chat/stream` and watch the SSE frames arrive.
3. **Break** it on purpose — a malformed request and an unavailable-MCP scenario —
   and confirm it degrades (422/400/safe message) instead of crashing.
4. Complete `starter/app.py`: a TODO-gapped copy of the app wiring where you fill
   in the endpoints and the lifespan handler.
5. **Read** the Docker + Compose + CI artifacts and (optionally) build the image.

## Files involved

```text
course/21_production_deployment/
├── README.md            ← you are here
├── concepts.md          ← read first: script→service, lifespan, SSE, health/ready, logging, Docker, CI
├── lab.md               ← the tasks (with real captured curl output)
├── starter/
│   └── app.py           ← your working file: complete the endpoints (has TODO markers)
├── solution/
│   ├── app.py           ← thin re-export of the production app (apps/api/main.py)
│   └── smoke.py         ← offline TestClient smoke script you can run
├── tests/
│   ├── test_solution.py ← proves the production app wiring works (always runs)
│   └── test_my_work.py  ← your completion gate (skips until starter TODOs are gone)
└── checklist.md         ← acceptance criteria
```

Production code you deploy (read, don't edit): `apps/api/main.py`,
`apps/api/safety.py`, `deploy/Dockerfile`, `deploy/docker-compose.yml`,
`deploy/README.md`, `.github/workflows/ci.yml`, `tests/test_api.py`.

Shared library you compose (read, don't edit): `src/techcorp_agent/capstone/`,
`src/techcorp_agent/memory/`, `src/techcorp_agent/streaming/`,
`src/techcorp_agent/config.py`.

## Commands

```bash
# From the repository root.

uv sync

# Run the service (offline, no Docker, no key):
uv run uvicorn apps.api.main:app --port 8000
#   then in another terminal: curl -s http://localhost:8000/health

# Prove the app imports and runs, offline, with no server at all:
uv run python course/21_production_deployment/solution/smoke.py

# Test this module (offline; your gate skips until the starter TODOs are gone):
uv run pytest course/21_production_deployment -q

# The service's own offline suite (what CI runs for /chat, /ready, streaming, ...):
uv run pytest tests/test_api.py -q

# Optional — Docker path:
docker build -f deploy/Dockerfile -t techcorp-agent-api .
docker compose -f deploy/docker-compose.yml up --build
```
