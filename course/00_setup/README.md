[🗺 Course Roadmap](../../ROADMAP.html) · [01 LLM Fundamentals →](../01_llm_fundamentals/README.md)

# Module 00 — Environment and Repository Setup

## Objective

Get a fully working, verified course environment: pinned dependencies installed
with `uv`, a `.env` created from the template, the offline test suite green,
and proof that no secret can ever leave your machine via git. You finish by
writing a small **secrets audit script** — the first tool in your TechCorp
toolbox.

## Estimated difficulty

Beginner. No AI knowledge required; basic command-line comfort is enough.

## Prerequisites

- Python 3.11+ installed
- [uv](https://docs.astral.sh/uv/) installed (`brew install uv` on macOS, or
  see the install page for other platforms)
- Git installed
- **No API key required** — this module (and the whole default course path)
  runs fully offline

## What you will build

- A verified environment: `make verify` reports everything required as ready
- A green offline test suite: `make test` passes without any API key
- `starter/check_secrets.py` completed into a working secrets audit that
  checks `.env` handling and scans the repo for leaked API keys

## Files involved

| File | Role |
|---|---|
| `course/00_setup/concepts.md` | Read first — environments, pinning, `.env`, offline mode, pytest layout |
| `course/00_setup/lab.md` | The step-by-step lab |
| `course/00_setup/starter/check_secrets.py` | Your work: complete the secrets audit |
| `course/00_setup/solution/check_secrets.py` | Reference implementation (peek only after trying) |
| `course/00_setup/tests/` | Automated checks for the solution and for your work |
| `course/00_setup/checklist.md` | Acceptance criteria |
| `Makefile`, `.env.example`, `scripts/verify_environment.py` | Repo infrastructure you will use |

## Commands

Run these from the repository root:

```bash
make setup                                   # install pinned deps, create .env
make verify                                  # environment report
make test                                    # offline test suite
uv run python course/00_setup/starter/check_secrets.py    # your audit script
uv run pytest course/00_setup -q             # this module's tests
```

When the checklist passes, tick Module 00 off in
[ROADMAP.html](../../ROADMAP.html) and move on to
[Module 01 — LLM Fundamentals](../01_llm_fundamentals/README.md).
