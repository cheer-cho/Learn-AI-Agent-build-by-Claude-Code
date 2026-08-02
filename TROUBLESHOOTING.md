# Troubleshooting

Start with `make verify` — it reports exactly which component needs attention.

## Setup

**`uv: command not found`** — install uv: `brew install uv` (macOS) or see
https://docs.astral.sh/uv/getting-started/installation/

**`ModuleNotFoundError: techcorp_agent`** — the project package isn't
installed: run `uv sync` (or `make setup`). If it persists:
`uv sync --reinstall-package techcorp-agent`.

**Wrong Python version** — this repo pins 3.12 in `.python-version`;
uv downloads it automatically if missing.

## Environment variables

**"No API key configured"** — expected in offline mode. To go live, edit
`.env` (create it with `cp .env.example .env`) and set `OPENAI_API_KEY`.

**Key set but still offline** — check `TECHCORP_OFFLINE` isn't `true` in
`.env` or your shell; shell variables override `.env`.

**Authentication failed (401)** — key is wrong/expired, or it belongs to a
different endpoint than `OPENAI_BASE_URL` points at.

**Could not reach the provider** — check network; if using a custom
`OPENAI_BASE_URL` (Ollama, OpenRouter), confirm it's running and includes the
`/v1` suffix where required.

## Models & embeddings

**First embedding call is slow / downloads** — sentence-transformers fetches
the model once (~90 MB), then caches it. Set `TECHCORP_OFFLINE=true` to use
hash embeddings instead (no download, no semantics).

**"Collection was indexed with X but you are querying with Y"** — you changed
embedding models after indexing. Rebuild: `make clean-index && make index`.

## Vector store

**Stale or weird retrieval results** — rebuild the index:
`make clean-index && make index`.

**Chroma errors after upgrading** — delete `.chroma/` and rebuild; the local
index is always disposable.

## Tests

**Default tests asking for an API key** — they never should; that's a bug in
your lab code calling the real client directly. Use `get_llm_client()` so
offline mode selects the mock.

**Run live tests deliberately** — `make test-live` (requires a key; spends
credits).
