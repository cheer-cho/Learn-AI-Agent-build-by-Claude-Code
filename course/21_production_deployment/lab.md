# Module 21 Lab — Ship the Agent as a Service

## Scenario

TechCorp's pilot went well and Act 3 begins: IT will host the assistant, but they
will not babysit a script. They need a service that starts with a documented
command, tells them whether it is healthy, streams answers to the web UI the
frontend team is building, and comes with a container image and CI. Your job is to
stand that service up, prove it degrades gracefully, and complete the app wiring.

Everything runs **offline** and **without Docker**. Work from the **repository
root** throughout.

## Learning objectives

By the end you can:

- Run a FastAPI agent service with Uvicorn and exercise it with curl.
- Explain and observe the difference between `/health` and `/ready`.
- Stream an answer over Server-Sent Events.
- Demonstrate graceful handling of malformed input and an unavailable MCP server.
- Complete the endpoint + lifespan wiring in `starter/app.py`.
- Read the Docker/Compose/CI artifacts and know what each one buys you.

## Setup

```bash
uv sync
# No .env changes needed — the service boots offline against the mock LLM.
```

---

## Step 1 — Run the API and hit `/health` and `/chat`

Start the service (leave it running; open a second terminal for curl):

```bash
uv run uvicorn apps.api.main:app --port 8000
```

Liveness and readiness:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
```

Captured output:

```text
{"status": "ok"}
{"ready": true}
```

Ask a grounded policy question, then a calculator question:

```bash
curl -s http://localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"question": "What is 17 * 4?"}'
```

Captured output:

```json
{
  "answer": "The result is 68.",
  "sources": [],
  "conversation_id": "46055c946e9646448e1d8d3ba0526d6f",
  "route": "calculator"
}
```

Note the `route` field — `calculator` here, `retrieval` for a policy question
(with populated `sources`), `orders` for an order lookup. The `conversation_id`
in the reply is the handle for the next step.

**Continue a conversation** by passing the id back:

```bash
CID=46055c946e9646448e1d8d3ba0526d6f
curl -s http://localhost:8000/chat -H 'content-type: application/json' \
  -d "{\"question\": \"What is the remote work policy?\", \"conversation_id\": \"$CID\"}"
```

The checkpointer (Module 15) reloads that thread's prior turns from SQLite and
threads them into the prompt — the same `conversation_id`, the same conversation.

---

## Step 2 — Stream a response

```bash
curl -N http://localhost:8000/chat/stream \
  -H 'content-type: application/json' \
  -d '{"question": "What is the remote work policy?"}'
```

`-N` disables curl's buffering so you see frames arrive live. Captured output:

```text
event: start
data: {"conversation_id": "ea7c078bc312498b86422cca4f75cf0a"}

event: node
data: {"node": "router", "summary": "node 'router' updated ['route', 'trace']"}

event: route
data: {"node": "router", "summary": "route selected: retrieval"}

event: node
data: {"node": "retrieval", "summary": "node 'retrieval' updated ['answer', 'sources', 'trace']"}

event: answer
data: {"answer": "...", "sources": ["hr-remote-work"], "conversation_id": "...", "route": "retrieval"}
```

Each `node`/`route` frame is one `AgentEvent` from
`techcorp_agent.streaming.stream_agent_events` — the *same* stream the CLI used in
Module 16 — re-encoded as SSE. The final `answer` frame carries the grounded
answer and its sources.

---

## Step 3 — Break it on purpose (graceful handling)

A production service is judged by how it fails. Three deliberate failures, none of
which should return a `500`:

**A malformed request** (missing `question`):

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  http://localhost:8000/chat -H 'content-type: application/json' -d '{}'
```

Captured output: `422` — Pydantic rejects the body and FastAPI returns a
structured `detail`, not a traceback. An empty/whitespace question returns `400`
with a clear reason from the safety layer.

**An unknown order** (`TC-9999`):

```bash
curl -s http://localhost:8000/chat -H 'content-type: application/json' \
  -d '{"question": "Where is order TC-9999?"}'
```

Captured output:

```json
{
  "answer": "No order found with id 'TC-9999'. Double-check the id (format TC-####) ...",
  "sources": [],
  "conversation_id": "66207b2601444382a20dde3332aacb3a",
  "route": "orders"
}
```

Status `200`, a safe message — the agent degrades instead of crashing.

**An unavailable MCP server.** The service builds its graph with **no MCP
registry** (the `--no-mcp` equivalent), so math and order questions run on the
in-process local tools. There is no MCP server to be down, and the endpoint can
never crash on one — try `{"question": "What is 10 * 5?"}` and you still get
`"50"`. `tests/test_api.py::test_unavailable_mcp_server_does_not_crash_the_endpoint`
asserts exactly this.

Run the service's own offline suite to see all of this asserted:

```bash
uv run pytest tests/test_api.py -q
```

---

## Step 4 — Complete `starter/app.py`

Open `starter/app.py`. It is the app wiring with the endpoint bodies and the
lifespan hook left as `TODO`s. Fill them in (the reference is `apps/api/main.py`),
then run your gate:

```bash
uv run pytest course/21_production_deployment -q
```

`tests/test_my_work.py` skips until every `TODO` marker is gone, then runs the
same behavioral checks against *your* app object.

---

## Step 5 (optional) — Build and run the Docker image

```bash
docker build -f deploy/Dockerfile -t techcorp-agent-api .
docker run --rm -p 8000:8000 --env-file .env techcorp-agent-api
# or, with a persistent index volume:
docker compose -f deploy/docker-compose.yml up --build
```

Then re-run the Step 1 curls against the containerized service. Read
`deploy/README.md` for the full endpoint table and config vars, and skim
`deploy/Dockerfile` to see the multi-stage build and non-root user.

---

## Step 6 — Read the CI workflow

Open `.github/workflows/ci.yml`. Trace what runs on every push/PR: `uv sync`,
`ruff check`, `ruff format --check`, `pytest -q`. Note that it sets
`TECHCORP_OFFLINE: "true"` and never selects the `live` marker — CI is
deterministic, free, and secret-free, and it runs the *same* suite you run
locally.

---

## Debugging hints

- **`Address already in use` / port 8000 taken.** Another process (or a previous
  Uvicorn) is on the port. Pick another: `uv run uvicorn apps.api.main:app
  --port 8001`, or find and stop the holder: `lsof -i :8000`.
- **`/ready` returns 503.** The lifespan handler has not finished (or you are
  hitting it before startup). Give it a second; in tests, remember `/ready` is
  only `200` **inside** a `with TestClient(app):` block.
- **`ModuleNotFoundError: No module named 'apps'`.** Run from the **repo root** so
  `apps/` is importable, or use the provided `uv run` commands. The test suite
  puts the repo root on `sys.path` for you.
- **Index seems empty / answers abstain.** The offline store indexes `data/` on
  first use into `.chroma/capstone_v1`. If you cleared `.chroma`, the first
  request just rebuilds it (a one-time cost).
- **Streaming shows nothing with curl.** Add `-N` to disable curl's output
  buffering, otherwise it waits for the whole response.

## Stretch

- **A `/metrics` count endpoint.** `apps/api/main.py` already ships a tiny
  `GET /metrics` returning `{"conversations": N, "total_turns": M}` from the
  in-process budget counter. Extend it: add a per-route counter (how many
  `retrieval` vs `calculator` vs `orders` vs `general` turns), and add a test in
  the style of `tests/test_api.py`.
- Add a `POST /chat` request-size limit test that a 5000-character question
  returns `400` (the safety layer caps at 4000).
