# Module 00 Concepts — Environments, Dependencies, and Secrets

This module has no AI in it — on purpose. Every bug you hit later in the
course will land on top of the foundation you set up here, so it pays to
understand each layer before you stack agents on it.

## 1. Virtual environments — and why this course uses uv

A **virtual environment** is a private, per-project copy of the Python
interpreter plus its own package directory. Installing a package inside a
virtual environment does not touch your system Python or any other project.

Why it exists: Python can only have one version of a package importable at a
time. Without isolation, project A needing `pydantic 1.x` and project B
needing `pydantic 2.x` would fight over one shared install. Virtual
environments give each project its own sandbox (here: the `.venv/` directory
at the repo root).

**uv** is the tool this course uses to manage that sandbox. It replaces the
usual trio of `python -m venv` + `pip` + `pip-tools` with one fast binary:

- `uv sync` creates `.venv/` (if needed) and installs *exactly* the locked
  dependency set.
- `uv run <command>` runs a command inside the environment without you having
  to "activate" anything — no `source .venv/bin/activate` to forget.

Trade-off: uv is an extra tool to install, and it is newer than pip, so some
online advice won't mention it. In exchange you get speed (installs are
seconds, not minutes), reproducibility by default, and one less class of
"works on my machine" bug. If you already know pip: everything here still
works conceptually the same way — uv just does it faster and locks it down
harder.

> Misconception: *"I need to activate the venv before running anything."*
> Not with uv. `uv run pytest` and `make test` handle it for you. Activating
> still works if you prefer it, but every command in this course is written
> so you never have to.

## 2. Dependency pinning — `pyproject.toml` vs `requirements.lock`

Two files at the repo root describe dependencies, and they answer different
questions:

- **`pyproject.toml`** declares *intent*: "this project needs
  `langchain>=0.3`". Ranges keep the project installable as libraries evolve.
- **`uv.lock`** (and its exported twin **`requirements.lock`**) records
  *exactly* what was installed, down to the patch version of every transitive
  dependency — the dependencies of your dependencies.

**Pinning** means recording those exact versions so that every learner, on
every machine, on any day, installs the identical set. `uv sync` installs
from the lock file, which is why the course's tests behave the same for
everyone.

Trade-off: pinning trades freshness for reproducibility. You won't silently
get bug fixes (or new bugs) from upstream releases; updating is a deliberate
act (`uv lock --upgrade`). For a course — where "your output should match the
lab's expected output" matters — reproducibility wins.

> Misconception: *"`pyproject.toml` is enough; the lock file is redundant."*
> With only ranges, two people running install a week apart can get different
> versions and different behavior. The lock file is what makes an install
> repeatable.

## 3. Environment variables and `.env` files

An **environment variable** is a named string the operating system hands to a
process when it starts (e.g. `HOME`, `PATH`). Programs read them with
`os.environ`. They are the standard way to give a program *configuration that
should not live in code* — most importantly, secrets.

A **`.env` file** is a plain text file of `NAME=value` lines. It is a
convenience: instead of exporting variables in every new terminal, you write
them once in `.env` and a loader reads them at startup. In this repo,
`src/techcorp_agent/config.py` uses `pydantic-settings` to load `.env` into a
typed `Settings` object — so the rest of the codebase never touches raw
environment strings.

The repo ships **`.env.example`**: a committed *template* with every variable
name but no secret values. `make setup` copies it to `.env` for you. The
split exists so the shape of the configuration is shared, while the values
stay private.

> Misconception: *"`.env` gets uploaded when I push to GitHub."*
> It doesn't — and you can prove it. The repo's `.gitignore` contains a
> `.env` rule, which tells git to pretend the file does not exist. Two
> commands demonstrate it:
>
> ```bash
> git check-ignore .env   # prints ".env" → the ignore rule matches
> git ls-files | grep -x '.env'   # prints nothing → git tracks no such file
> ```
>
> `git ls-files` lists every file git would push; `.env` is not in it. Only
> files git *tracks* leave your machine. (Caveat: if someone force-adds it
> with `git add -f`, git will track it — which is exactly what your lab
> exercise, a secrets audit script, exists to catch.)

## 4. API keys, base URLs, and model identifiers

Three variables in `.env` describe *which* language model provider to talk to
and *how*:

- **API key** (`OPENAI_API_KEY`) — a secret token that authenticates you to a
  provider and bills your account. Treat it like a password. OpenAI keys, for
  example, start with the prefix `sk-` followed by a long random string —
  a pattern your lab script will scan for.
- **Base URL** (`OPENAI_BASE_URL`) — the web address of the API server. The
  "OpenAI-compatible" API shape has become a de-facto standard, so the same
  client code can point at OpenAI itself, OpenRouter, or a local
  [Ollama](https://ollama.com) server (`http://localhost:11434/v1`) just by
  changing this one URL.
- **Model identifier** (`OPENAI_MODEL`) — the name of the specific model to
  use, e.g. `gpt-4o-mini` or `llama3.2`. One provider hosts many models with
  different capabilities and prices.

### Why the course works without a key — offline mode

Every module runs by default against a **mock adapter**: a stand-in class
(`MockLLMClient`) with the same interface as a real LLM client, returning
deterministic scripted responses. `Settings.offline` in
`src/techcorp_agent/config.py` is the single switch: it is true whenever no
API key is set, or when `TECHCORP_OFFLINE=true` forces it.

Why bother? Three reasons: **cost** (tests that hit a paid API spend money on
every run), **determinism** (real models give different answers each time —
useless for automated tests), and **accessibility** (you can do the entire
course on a plane). The trade-off is honesty: a mock never shows you real
model behavior, which is why from Module 02 onward each lab offers an
optional live path when you do have a key.

## 5. How pytest is organized here

**pytest** is the test runner used throughout the course. Configuration lives
in `pyproject.toml` under `[tool.pytest.ini_options]`:

- `testpaths = ["tests", "course"]` — running `make test` collects the
  infrastructure suite in `tests/` *and* every module's `course/*/tests/`.
- `addopts = "-m 'not live' -q"` — by default pytest **deselects** any test
  marked `live`. A *marker* is a label attached to a test; the `live` marker
  means "this test calls a real LLM API and spends credits". So `make test`
  is always free and offline; `make test-live` opts in to the marked tests.

Each course module ships two test files with fixed roles:

- `tests/test_solution.py` runs against `solution/` and must always pass — it
  proves the reference implementation works.
- `tests/test_my_work.py` runs against `starter/` — *your* code. It
  auto-skips while your starter still contains `TODO` markers, then becomes
  your completion gate once you start working.

## 6. Repository navigation

```text
claud-build-ai-course/
├── ROADMAP.html          # visual roadmap + checkpoint tracker (home base)
├── Makefile              # setup / verify / test / lint entry points
├── pyproject.toml        # dependency intent + pytest & ruff config
├── uv.lock, requirements.lock   # exact pinned versions
├── .env.example → .env   # config template → your private copy (gitignored)
├── course/               # 23 modules; each: README, concepts, lab,
│                         #   starter/, solution/, tests/, checklist
├── src/techcorp_agent/   # shared library every module builds on
│                         #   (config.py, llm/, embeddings/, vectorstore/, …)
├── data/                 # the fictional TechCorp document corpus
├── scripts/              # verify_environment.py, build_index.py
├── tests/                # infrastructure test suite
├── apps/, deploy/        # production service & packaging (Levels 4–5)
└── artifacts/            # generated reports
```

The pattern to internalize: **modules teach, `src/techcorp_agent/` keeps.**
Code you write in a module's `starter/` is your exercise; the reusable,
tested version of each capability lives in the shared library so later
modules can import it instead of re-implementing it.

## Common misconceptions — recap

| Misconception | Reality |
|---|---|
| "`.env` is uploaded with git" | It's gitignored; `git ls-files` proves git doesn't track it |
| "I must activate the venv" | `uv run` / `make` targets handle it |
| "The lock file is redundant" | It's what makes installs reproducible across machines and time |
| "No API key means the course is crippled" | The default path is designed offline-first; live calls are an optional add-on |
| "Mock tests prove the agent works with a real model" | They prove logic, not model behavior — that's a deliberate trade-off |
