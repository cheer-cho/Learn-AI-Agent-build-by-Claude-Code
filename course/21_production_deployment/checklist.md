# Module 21 Checklist — Production Deployment

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words, the difference between a script and a service, and why the index/graph must be built **once** at startup rather than per request.
- [ ] I can state the difference between **liveness** (`/health`) and **readiness** (`/ready`) and what an orchestrator does with each (restart vs pull-from-LB).
- [ ] I ran `uv run uvicorn apps.api.main:app` and got `{"status": "ok"}` from `/health` and `{"ready": true}` from `/ready`.
- [ ] `POST /chat` with a policy question returned a non-empty `answer`, a `sources` list, a `conversation_id`, and `route: "retrieval"`.
- [ ] A calculator question routed to `calculator` and an order question to `orders`; I saw the `route` field change.
- [ ] I continued a conversation by passing the returned `conversation_id` back on a second `POST /chat`, and understand the checkpointer threads history by that id.
- [ ] I streamed a response from `/chat/stream` with `curl -N` and saw multiple SSE frames ending in an `event: answer` frame.
- [ ] I sent a malformed request (missing `question`) and got `422` — a clear error, not a crash — and an empty question returned `400`.
- [ ] I confirmed an unknown order (`TC-9999`) returns a safe `200` message, and that the service uses local tools so an unavailable MCP server cannot crash it.
- [ ] I understand the service logs only **metadata** (request id, route, lengths, timings) and never the question text, answer text, or any API key.
- [ ] `starter/app.py` has no remaining `TODO` markers, and `uv run pytest course/21_production_deployment -q` passes with `test_my_work.py` no longer skipped.
- [ ] `uv run pytest tests/test_api.py -q` (the service's own offline suite) passes.
- [ ] `uv run python course/21_production_deployment/solution/smoke.py` prints all PASS and `SMOKE OK`.
- [ ] I read `deploy/Dockerfile` and can name why it is multi-stage and runs as a non-root user, and I read `deploy/docker-compose.yml` and can say why the Chroma index needs a persistent volume.
- [ ] (Optional) I built and ran the Docker image and hit the same endpoints against the container.
- [ ] I read `.github/workflows/ci.yml` and can trace what runs on every push/PR (uv sync, ruff check, ruff format --check, pytest) and why it is offline and secret-free.
- [ ] I can explain the trade-off between an in-process index (this service) and an external vector DB, and name when the in-process choice stops paying off.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 21.
