# Build Report — TechCorp AI Agents Lab Course

**Status: complete.** All 23 modules built, tested, and documented. The full
offline test suite passes and every module solution runs without an API key.

## What was created

A project-based course that takes a learner from zero to a deployed, evaluated,
multi-agent AI system — one continuous project, the **TechCorp Knowledge Agent**,
built lab by lab across 5 levels.

- **23 course modules** (`course/00_*` … `course/22_hero_capstone/`), each with
  `README.md` (roadmap nav), `concepts.md`, `lab.md`, runnable `starter/` with
  TODOs, working `solution/`, `tests/`, and `checklist.md`.
- **16 shared packages** under `src/techcorp_agent/` that every module reuses:
  `config`, `llm` (provider adapter + offline mock), `embeddings`
  (sentence-transformers + hash offline), `documents` (loader + chunking),
  `vectorstore` (ChromaDB), `rag` (pipeline + advanced), `evaluation`, `tools`,
  `mcp_servers` (calculator + orders + registry), `agents` (supervisor +
  specialists), `memory`, `streaming`, `safety`, `tracing`, `capstone`,
  `capstone_v2`.
- **72 source files, 69 test files, 470 passing tests.**
- **Fictional TechCorp dataset**: 17 policy documents, mock orders, a 33-example
  evaluation set, scripted memory conversations, and quarantined
  prompt-injection docs for the security lab.
- **Production service**: FastAPI app (`apps/api/`), Docker + compose
  (`deploy/`), and a GitHub Actions CI workflow (`.github/workflows/ci.yml`).
- **8 generated artifacts** under `artifacts/` (evaluation, chunking, retrieval
  improvement, multi-agent comparison, injection defense, experiment reports).
- **Interactive roadmap** (`ROADMAP.html`) with per-module checkpoints.
- **Career assets** in the hero capstone: `ARCHITECTURE.md`, `DEMO_SCRIPT.md`,
  `PORTFOLIO_README.md`, `INTERVIEW_PREP.md`.

## Repository tree (top level)

```text
ai-agents-lab-course/
├── ROADMAP.html              # start here — visual roadmap + checkpoints
├── README.md  COURSE_MAP.md  LEARNER_GUIDE.md  INSTRUCTOR_NOTES.md
├── TROUBLESHOOTING.md  BUILD_REPORT.md
├── pyproject.toml  requirements.lock  Makefile  .env.example
├── course/00_setup … 22_hero_capstone/     # 23 modules
├── src/techcorp_agent/       # 16 shared packages
├── apps/api/                 # FastAPI service
├── deploy/                   # Dockerfile, compose, CI
├── data/                     # TechCorp corpus, orders, evaluation, security_lab
├── tests/                    # infrastructure + package test suites
├── scripts/                  # verify_environment.py, build_index.py
└── artifacts/                # generated reports
```

## Commands to begin

```bash
make setup      # create env, install pinned deps, create .env
make verify     # confirm what's ready (all green offline)
make test       # run the offline suite (no API key)
open ROADMAP.html   # then start course/00_setup/README.md
```

## Test results

- `uv run pytest` → **470 passed, 157 skipped, 3 deselected.**
- Skips are the learner-gate tests (`test_my_work.py`) that activate once a
  learner replaces the TODOs in each `starter/`, plus a few environment-guarded
  cases. Deselected are the 3 `live` tests requiring a real API key.
- `ruff format --check` and `ruff check` are clean across the repo.
- `scripts/verify_environment.py` reports all required components ready.
- `make clean-index && make index` rebuilds the vector index (13 docs → 67
  chunks) successfully.

## Features requiring a live API key

Everything runs offline by default via deterministic mocks. A real
OpenAI-compatible key in `.env` unlocks:

- Real LLM answers in every lab (instead of the echo mock).
- The 3 `live`-marked tests (`pytest -m live`).
- Genuine generation-quality numbers in the Module 09 / 19 evaluations.

A free LangSmith key optionally enables live tracing in Module 19 (a local JSONL
trace fallback is used otherwise). Embeddings always run locally and free via
sentence-transformers (or hash embeddings with `TECHCORP_OFFLINE=true`).

## Known limitations

- Offline generation metrics are placeholders: the mock LLM echoes context, so
  answer-quality scores are only meaningful with a live key. Retrieval metrics
  are real offline. Each affected lab states this explicitly.
- With hash embeddings (offline), some semantic queries that need real meaning
  (e.g. "recover my account") retrieve less well than with sentence-transformers
  — this is taught, not hidden (Modules 05–06).
- On the small clean TechCorp corpus, advanced RAG techniques show large offline
  gains but little gain with real embeddings — the honest "when naive RAG is
  enough" lesson (Module 17, `artifacts/retrieval_improvement_report.md`).
- The optional web UI (`apps/web/`) is left as a hero-capstone stretch; the CLI
  and HTTP API are complete.

## Suggested next exercises

- Add your own TechCorp policy documents and re-run the Module 09 evaluation.
- Turn on a live key and compare offline vs live answers in the Module 08 RAG lab.
- Enable `advanced_rag=True` in the v2 capstone and measure the difference on
  your own questions.
- Build the optional `apps/web/` UI against the existing `/chat/stream` endpoint.
- Deploy the service with `deploy/docker-compose.yml` and hit it over HTTP.

## Build notes

Built with a hybrid orchestration: shared infrastructure and dataset assembled
first, then module content generated by parallel agents and integration-tested
before each milestone commit. Library APIs were verified against the installed
(newer-than-documented) versions — LangChain 1.3, LangGraph 1.2, MCP 2.0 — rather
than assumed; the MCP 2.0 breaking changes (`MCPServer` replacing `FastMCP`,
snake_case fields, `is_error` results) are reflected throughout Modules 12–14.
Two duplicate packages from concurrent-agent collisions were removed, keeping the
canonical versions the course modules import.
