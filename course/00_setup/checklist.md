# Module 00 Checklist — Environment and Repository Setup

Work through [lab.md](lab.md) first. Every box must be checkable before you
move on; each is verifiable with a command, not a feeling.

## Environment

- [ ] `uv --version` prints a version (uv is installed and on PATH)
- [ ] `make setup` completes without errors and prints `Setup complete`
- [ ] `.env` exists at the repo root, created from `.env.example`, with
      `OPENAI_API_KEY` left empty (offline mode)
- [ ] `make verify` exits 0; every line reports `ready` or
      `optional — not configured`, and you can explain what each check does
- [ ] `make test` passes with no API key configured, and you can explain why
      the `live`-marked tests were deselected

## Secrets hygiene

- [ ] `git check-ignore .env` prints `.env` (the ignore rule matches)
- [ ] `git ls-files` does not list `.env` (git tracks no such file)
- [ ] You can explain to a teammate why those two facts together mean `.env`
      never reaches a remote

## Starter exercise

- [ ] `starter/check_secrets.py` has no remaining `TODO` markers
- [ ] `uv run python course/00_setup/starter/check_secrets.py` prints four
      `[PASS]` lines and exits 0 (`echo $?` prints `0`)
- [ ] Your script reports offending *file paths only* — it never prints a
      secret value
- [ ] `uv run pytest course/00_setup -q` passes: `test_my_work.py` runs (no
      longer skipped) and `test_solution.py` stays green

## Concepts (self-check, from [concepts.md](concepts.md))

- [ ] You can state the difference between `pyproject.toml` and
      `requirements.lock` / `uv.lock` in one sentence each
- [ ] You can name the single condition under which the course uses the mock
      LLM instead of a real provider (see `Settings.offline` in
      `src/techcorp_agent/config.py`)
- [ ] You can say what `OPENAI_BASE_URL` changes and why the same client code
      can talk to OpenAI, OpenRouter, or a local Ollama

## Done

- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 00.
