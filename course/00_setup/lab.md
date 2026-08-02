# Lab 00 — First Day at TechCorp

## Scenario

Welcome aboard. It's your first day as a junior AI engineer at **TechCorp**,
and your team lead has one rule for new hires: *nobody touches the Knowledge
Agent codebase until their environment is verified and they've proven they
can handle secrets safely.* Last quarter an intern at a competitor pushed an
API key to a public repo; it was scraped and abused within minutes. Your
onboarding ticket therefore has two parts: get the repo running, then build a
small **secrets audit** script the whole team can run before every commit.

## Learning objectives

By the end of this lab you can:

1. Set up a reproducible Python environment with uv and pinned dependencies.
2. Configure a project through `.env` without exposing secrets.
3. Read and act on the `make verify` environment report.
4. Run the offline test suite and explain why it needs no API key.
5. Prove — with git commands — that secrets cannot leave your machine.
6. Write a script that shells out to git and scans files for key patterns.

Read [concepts.md](concepts.md) first. All commands run from the
**repository root**.

---

## Step 1 — Install uv (if you don't have it)

```bash
uv --version
```

**Expected output:** a version line such as `uv 0.5.x` (any recent version is
fine). If instead you see `command not found`, install it:

```bash
# macOS
brew install uv
# or any platform
curl -LsSf https://astral.sh/uv/install.sh | sh
```

> **Debugging hint:** after the curl install, uv lands in `~/.local/bin`.
> If the shell still can't find it, open a new terminal or add
> `export PATH="$HOME/.local/bin:$PATH"` to your shell profile.

## Step 2 — Install the environment

```bash
make setup
```

**Expected output:** uv resolves and installs the pinned packages (first run
takes a little while — it downloads everything; re-runs are near-instant),
then:

```text
Setup complete. Next: make verify
```

> **Debugging hint:** `error: No interpreter found for Python 3.11` means
> your Python is too old — install 3.11+ (`brew install python@3.12` or
> `uv python install 3.12`) and re-run. If a package fails to build, check
> [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md).

## Step 3 — Confirm `.env` was created from the template

`make setup` copies `.env.example` to `.env` if it doesn't exist. Verify:

```bash
ls -la .env
diff .env .env.example && echo "identical to template"
```

**Expected output:** the file exists, and (on a fresh setup) `identical to
template`. Open `.env` in your editor and read the comments — leave every
value as-is for now. **No key goes in this file today.**

> **Debugging hint:** no `.env`? Create it directly with
> `cp .env.example .env`. If `diff` shows changes, that's fine too — it just
> means the file already existed; make sure `OPENAI_API_KEY` is empty for
> this module.

## Step 4 — Run the environment report (and actually read it)

```bash
make verify
```

**Expected output:** a report like this — read *every* line and make sure you
can say what each check verifies (concepts.md §4–5 has the answers):

```text
TechCorp AI Agents Lab — environment check
============================================================
  [ready                     ] Python version: Python 3.12.x
  [ready                     ] Required packages: all 9 required packages import
  [ready                     ] .env file: .env exists
  [optional — not configured ] LLM provider: no OPENAI_API_KEY — offline mock mode active (fine for most labs)
  [ready                     ] Offline mode: mock LLM works — default tests run without API credits
  [ready                     ] TechCorp dataset: 13 TechCorp documents load cleanly
  [ready                     ] Vector store: ChromaDB writes and queries locally
  [optional — not configured ] LangSmith (optional): no LangSmith key — local trace fallback used in Module 19
============================================================
Everything required is ready. Start with course/00_setup/README.md
```

**Checkpoint:** the exit status is 0 (`echo $?` prints `0`), and the two
`optional` lines are *expected* — they are not failures.

> **Debugging hint:** any `NEEDS ATTENTION` line tells you the fix inline
> (usually `make setup` or copying `.env`). Open
> `scripts/verify_environment.py` to see exactly what each check does — it's
> short and readable.

## Step 5 — Run the offline test suite

```bash
make test
```

**Expected output:** a quiet pytest run ending in a line like

```text
NN passed, M deselected in X.XXs
```

**Checkpoint:** zero failures, zero errors — and no API key configured.
The `deselected` tests are the `live`-marked ones pytest skips by default.

> **Debugging hint:** `ImportError` or `ModuleNotFoundError` almost always
> means the suite ran outside the project environment — use `make test` or
> `uv run pytest`, never bare `pytest`.

## Step 6 — Confirm secrets are not committed

Prove the two claims from concepts.md §3 yourself:

```bash
git check-ignore .env
git ls-files | grep -x '.env' ; echo "grep exit: $?"
```

**Expected output:** the first command prints `.env` (the ignore rule
matches). The second prints nothing and `grep exit: 1` — grep "failing" to
find `.env` in git's tracked files is exactly what you want.

**Checkpoint:** you can explain to a teammate why these two commands together
mean `.env` will never be pushed.

> **Debugging hint:** if `git check-ignore .env` prints nothing and exits 1,
> the ignore rule is missing — check that the repo root `.gitignore` has a
> `.env` line. If `git ls-files` *does* show `.env`, someone force-added it:
> `git rm --cached .env` untracks it without deleting your local file.

## Step 7 — Complete the starter exercise: the secrets audit

Now automate Step 6 — and go further. Open
[`starter/check_secrets.py`](starter/check_secrets.py). It's runnable but
incomplete: check (a) is implemented as a worked example; checks (b), (c),
and (d) are `# TODO:` blocks for you. The script must:

- (a) verify `.env` exists — *done for you*
- (b) verify `.env` is matched by `.gitignore` — shell out to
  `git check-ignore .env` and inspect the return code
- (c) verify `git ls-files` does not list `.env`
- (d) scan every file under `src/` and `course/` for strings that look like
  leaked API keys (`sk-` followed by a long run of key characters)

Run it as you work:

```bash
uv run python course/00_setup/starter/check_secrets.py
```

**Expected output when complete:** four `[PASS]` lines, a `Secrets audit
passed.` summary, and exit code 0 (`echo $?`). While incomplete, unfinished
checks report `[FAIL] ... TODO` and the script exits 1 — that's the design:
an audit that isn't finished must not pretend the repo is clean.

Then run this module's tests. They skip while TODO markers remain and become
your completion gate afterwards:

```bash
uv run pytest course/00_setup -q
```

**Checkpoint:** all tests in `tests/test_my_work.py` pass (no longer
skipped), and `tests/test_solution.py` still passes.

> **Debugging hint:** for (b) and (c), read Python's `subprocess.run`
> documentation — you want `capture_output=True, text=True` and either
> `.returncode` or `.stdout`. Remember `git check-ignore` signals "ignored"
> purely via return code 0. For (d), `re.search` with the pattern already
> defined at the top of the file is enough; report the *file path only* —
> printing the matched key would leak the very secret you found. Never print
> secret values — report presence/absence only. Stuck after a real attempt?
> Compare with [`solution/check_secrets.py`](solution/check_secrets.py).

---

## Stretch exercise — point the course at a local model

The client config is provider-agnostic (concepts.md §4). If your machine can
run [Ollama](https://ollama.com):

1. Install Ollama and pull a small model, e.g. `ollama pull llama3.2:1b`.
2. In `.env` set:
   `OPENAI_BASE_URL=http://localhost:11434/v1`,
   `OPENAI_MODEL=llama3.2:1b`, and `OPENAI_API_KEY=ollama` (Ollama accepts
   any non-empty string — the variable just has to be set).
3. Re-run `make verify` and watch the **LLM provider** line flip from
   `optional — offline mock mode` to `ready — live provider responded`.
4. Revert `.env` (empty the three values) when done, and confirm `make
   verify` returns to offline mode — the rest of the course assumes the
   default offline configuration unless a lab says otherwise.

No local model? Skip this — nothing later depends on it.

When everything above checks out, work through [checklist.md](checklist.md).
