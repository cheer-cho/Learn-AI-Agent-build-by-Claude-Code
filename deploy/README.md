# Deploying the TechCorp Knowledge Agent API

The agent from Modules 14–20 is packaged here as a monitored HTTP service
(`apps/api/main.py`). This directory holds the deployment artifacts. **Docker is
optional** — the service runs perfectly with just `uv` and Uvicorn.

## Run it — without Docker (the fast path)

From the **repository root**:

```bash
uv sync
uv run uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
# add --reload while developing
```

It boots **offline** against the deterministic mock LLM — no API key required.
Open <http://localhost:8000/docs> for the interactive OpenAPI UI.

## Run it — with Docker

Build and run from the **repository root** (the build context must include
`src/` and `apps/`):

```bash
docker build -f deploy/Dockerfile -t techcorp-agent-api .
docker run --rm -p 8000:8000 --env-file .env techcorp-agent-api
```

Or with Compose (also from the repo root), which adds a **persistent volume** for
the Chroma index and the conversation-memory DB so they survive restarts:

```bash
docker compose -f deploy/docker-compose.yml up --build
```

The `chroma-data` named volume is mounted at `/app/.chroma`; the index is built
once and then reused across `docker compose down` / `up` cycles.

## Configuration (environment variables)

Config comes from the environment (Compose reads the repo-root `.env`). All are
optional — the defaults keep the service offline and self-contained.

| Variable | Default | Purpose |
|---|---|---|
| `TECHCORP_OFFLINE` | `true` in the image | Force the mock LLM. Set `false` **and** provide `OPENAI_API_KEY` to serve with a live model. |
| `OPENAI_API_KEY` | *(empty)* | Live provider key. Never commit it — `.env` is gitignored. |
| `OPENAI_BASE_URL` | *(empty)* | Point at OpenAI, OpenRouter, or a local Ollama. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model id on that endpoint. |
| `TECHCORP_MEMORY_DB` | temp file / `/app/.chroma/api_memory.sqlite3` in the image | SQLite path for conversation memory; put it on the mounted volume to persist threads. |

The service **never logs** the question text, the answer, or any key — only
metadata (request id, route, timings, lengths). Keeping secrets and user content
out of logs is a guardrail (Module 20), not an afterthought.

## Endpoints

| Method & path | Purpose | Body / notes |
|---|---|---|
| `GET /health` | **Liveness** — is the process up? Cheap, dependency-free. | → `{"status":"ok"}` |
| `GET /ready` | **Readiness** — is the index loaded? `503` until warm. | → `{"ready":true}` |
| `POST /chat` | Grounded answer + sources + conversation id. | `{"question": "...", "conversation_id"?: "..."}` |
| `POST /chat/stream` | Same, as Server-Sent Events (`text/event-stream`). | same body; frames stream as the graph runs |
| `GET /metrics` | Tiny counters: conversations seen, total turns. | → `{"conversations":N,"total_turns":M}` |

### curl examples

```bash
# Liveness / readiness
curl -s http://localhost:8000/health   # {"status": "ok"}
curl -s http://localhost:8000/ready    # {"ready": true}

# A grounded policy question (returns answer + sources + conversation_id)
curl -s http://localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"question": "What is the remote work policy?"}'

# A calculator question routes to the calculator tool
curl -s http://localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"question": "What is 17 * 4?"}'
# {"answer":"The result is 68.","sources":[],"conversation_id":"...","route":"calculator"}

# Continue a conversation by reusing its id
curl -s http://localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"question": "And what about international remote work?", "conversation_id": "<id from a previous reply>"}'

# Stream the answer as Server-Sent Events (-N disables curl buffering)
curl -N http://localhost:8000/chat/stream \
  -H 'content-type: application/json' \
  -d '{"question": "What is the remote work policy?"}'
```

Streaming output looks like this (one frame per graph step, then a final
`answer` frame):

```text
event: start
data: {"conversation_id": "ea7c078bc312498b86422cca4f75cf0a"}

event: node
data: {"node": "router", "summary": "node 'router' updated ['route', 'trace']"}

event: route
data: {"node": "router", "summary": "route selected: retrieval"}

event: answer
data: {"answer": "...", "sources": ["hr-remote-work"], "conversation_id": "...", "route": "retrieval"}
```

## Graceful behavior (nothing here returns a 500)

- **Malformed request** (missing `question`) → `422` with a structured `detail`.
- **Empty question** → `400` with a clear reason.
- **Unknown order** (`TC-9999`) → `200` with a safe "no such order" message.
- **No MCP servers** → math/order questions fall back to the in-process local
  tools; the service never depends on a running MCP server to answer.

## CI

`.github/workflows/ci.yml` runs on every push and PR: `uv sync`, `ruff check`,
`ruff format --check`, and the offline `pytest` suite — no secrets, no live
tests. The exact suite gating this service lives in `tests/test_api.py`.
