# TechCorp AI Agents Lab Course

Learn AI engineering from **zero to hero** by building one continuous project:
the **TechCorp Knowledge Agent** — from your first LLM API call to a deployed,
evaluated, multi-agent production system.

**🗺 Your home base is [ROADMAP.html](ROADMAP.html)** — open it in a browser to
see the full path, jump into any module, and tick off checkpoints as you go.

## Quick start

```bash
make setup      # create the environment, install pinned dependencies, create .env
make verify     # see what's ready and what needs configuration
make test       # run the offline test suite (no API key needed)
```

Then start with [Module 00](course/00_setup/README.md).

## What you need

- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (`brew install uv`)
- **No API key required** for the default path — every lab runs offline against
  deterministic mock adapters, and the default tests never spend credits.
- Optional: any OpenAI-compatible API key in `.env` to see real model behavior
  (recommended from Module 02 onwards), and a free LangSmith key for Module 19.

## Repository layout

| Path | What it is |
|---|---|
| `ROADMAP.html` | Visual roadmap + checkpoint tracker (start here) |
| `COURSE_MAP.md` | Module-by-module map and career outcomes |
| `course/` | 23 modules: concepts, labs, starter code, solutions, tests |
| `src/techcorp_agent/` | Shared infrastructure every module builds on |
| `data/` | The fictional TechCorp document corpus and evaluation sets |
| `tests/` | Infrastructure test suite (`make test`) |
| `scripts/` | `verify_environment.py`, `build_index.py` |
| `apps/`, `deploy/` | Production service and packaging (Levels 4–5) |
| `artifacts/` | Generated reports (evaluations, comparisons) |

## Rules of the road

- Copy `.env.example` to `.env`; never commit `.env` (already gitignored).
- Work in each module's `starter/`; peek at `solution/` only after trying.
- A module is "done" when its `checklist.md` passes and its tests are green —
  then tick it off in [ROADMAP.html](ROADMAP.html).
- Stuck? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
