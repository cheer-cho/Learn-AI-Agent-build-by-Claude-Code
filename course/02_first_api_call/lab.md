# Module 02 Lab — TechCorp's First Scripted Assistant Call

## Scenario

Your team lead at TechCorp wants a proof of concept before anyone talks about "agents": one script that asks the company assistant a question and prints not just the answer, but the evidence — which model replied, how many tokens it took, and what the request cost. It must run on every engineer's laptop, including the ones with no API key, and when something is misconfigured it must say what to fix instead of dumping a stack trace.

You will implement `starter/first_call.py`. The shared library (`src/techcorp_agent/`) already provides `Settings`, `ChatMessage`/`ChatResult`, the client adapter, and `estimate_cost_usd` — your job is to wire them together correctly.

## Learning objectives

By the end you can:

- Load provider configuration from the environment instead of hard-coding it
- Construct a valid system + user conversation
- Extract content from a chat response without assuming it is a plain string
- Read token usage defensively and convert it into an estimated cost
- Turn authentication and network failures into actionable messages

## Setup

```bash
uv sync                      # if you haven't already
cp .env.example .env         # if you haven't already; blank key = offline mode
```

Run commands from the repository root.

- **Run your work:** `uv run python course/02_first_api_call/starter/first_call.py`
- **Test:** `uv run pytest course/02_first_api_call -q`
- **Peek at the target behavior anytime:** `uv run python course/02_first_api_call/solution/first_call.py` (but attempt each task before reading solution code)

## Tasks

Open `starter/first_call.py`. Each TODO below maps to one.

### Task 1 — Read configuration from the environment

Already wired in `main()`: `get_settings()` returns a `techcorp_agent.config.Settings` loaded from `.env`. Your job here is only to *verify you understand it*: open `src/techcorp_agent/config.py` and find where the API key, model, and the two cost rates come from. Nothing to type yet.

### Task 2 — Initialize the client

Also wired: `get_llm_client(settings)` returns the mock client when offline and the real `OpenAIChatClient` when a key is set. Note what `main()` prints as `client:` — you will see it change if you ever add a key. Open `src/techcorp_agent/llm/factory.py` to see the decision.

### Task 3 — Build and send a system + user message

Implement `build_messages(question)`: return a list of `ChatMessage` objects — a `system` message containing `SYSTEM_PROMPT` ("You are TechCorp's internal assistant.") first, then a `user` message containing the question.

Implement `run_request(client, messages)`: call `client.complete(...)` with the messages and `temperature=0.0`, return its `ChatResult`.

### Task 4 — Print the assistant's content

Already in `main()` once Tasks 3 works: the reply prints under `--- Assistant ---`. Run the script and confirm you get output (Checkpoint A).

### Task 5 — Safely inspect the full response

Implement `inspect_result(result)`: print `result.model` and `result.content` (use `!r` so an empty reply is visible as `''`). Then handle `result.raw`:

- if it is `None` (offline mock), say the raw provider payload is unavailable;
- otherwise print the first choice's `finish_reason` — **without** indexing `choices` unless it is non-empty.

### Task 6 — Extract token usage, handling absence

In `summarize_usage(result, settings)`: if `result.usage` is `None`, print that usage was not reported and return `None` — do not crash, do not invent numbers. Otherwise print `input_tokens`, `output_tokens`, and `total_tokens`.

### Task 7 — Estimate the request cost

Still in `summarize_usage`: when usage exists, compute the cost with `estimate_cost_usd(usage, settings.cost_input_per_mtok, settings.cost_output_per_mtok)`, print it (6 decimal places reads well for sub-cent amounts), and return it.

### Task 8 — Handle authentication and network errors

In `main()`: wrap the `run_request(...)` call in `try/except ProviderError`. On error, print the exception's message to `sys.stderr` — the adapter already phrases it to name the `.env` setting to fix — and return `1`. Verify with the broken-key experiment in Checkpoint C.

## Checkpoints

### Checkpoint A — after Tasks 3-4

`uv run python course/02_first_api_call/starter/first_call.py` prints (offline):

```text
client: mock-offline

--- Assistant ---
[offline mock] I received your message: 'In one sentence, what should I do when a customer asks for a refund?'. Configure OPENAI_API_KEY in .env for real answers.
```

…then stops at the next `NotImplementedError`. That's expected — keep going.

### Checkpoint B — after Tasks 5-7

The full offline run looks like this (your token counts must match — the mock is deterministic):

```text
client: mock-offline

--- Assistant ---
[offline mock] I received your message: 'In one sentence, what should I do when a customer asks for a refund?'. Configure OPENAI_API_KEY in .env for real answers.

--- Full response (safely inspected) ---
model:   mock-offline
content: "[offline mock] I received your message: 'In one sentence, what should I do when a customer asks for a refund?'. Configure OPENAI_API_KEY in .env for real answers."
raw:     (no raw provider payload — offline mock client)

--- Usage & estimated cost ---
input tokens:  26
output tokens: 40
total tokens:  66
estimated cost: $0.000186 ($1.00/M input, $4.00/M output)
```

### Checkpoint C — after Task 8 (error handling)

Put a fake key in `.env` (`OPENAI_API_KEY=not-a-real-key`) and run the starter again. You must get a one-paragraph actionable message mentioning `OPENAI_API_KEY` (or the network, if you are offline) and exit code 1 — **no traceback**. Restore `.env` to a blank key afterwards.

### Checkpoint D — tests green

```bash
uv run pytest course/02_first_api_call -q
```

Expected once your TODOs are gone: all tests pass and nothing is skipped except the `live` test (deselected by default). While TODO markers remain, `test_my_work.py` skips — that skip disappearing is your progress bar.

## Debugging hints

- **`ValidationError` when constructing `ChatMessage`** → your `role` string isn't one of `system` / `user` / `assistant`. Check spelling and case.
- **`AttributeError: 'NoneType' object has no attribute ...` in `summarize_usage`** → you touched `result.usage.<field>` before the `None` check. The `None` branch must come first.
- **Cost prints as `$0.000000`** → you divided by 1M twice, or passed rates and tokens in the wrong argument order. Compare against a by-hand calculation: 26 × $1.00/M + 40 × $4.00/M = $0.000186.
- **`test_my_work.py` still skipping after you finished** → a `TODO` string is still present somewhere in `starter/first_call.py` (the gate is literal). Delete the marker comments you resolved.
- **Traceback instead of a friendly error in Checkpoint C** → your `except` catches the wrong type: the adapter raises `ProviderError` (from `techcorp_agent.llm.base`), not the SDK's exceptions.
- **`ModuleNotFoundError: techcorp_agent`** → run from the repository root with `uv run`, not from inside the module directory with bare `python`.

## Stretch exercise (live only — requires a real key)

Temperature is the randomness dial; make it visible. With a key in `.env`, extend your script (or a scratch copy) to send the *same* messages three times at `temperature=0.0` and three times at `temperature=1.0`, printing each reply.

- At 0.0 the three replies should be identical or nearly so.
- At 1.0 expect visible variance in wording — sometimes in substance.

Then decide: which setting does TechCorp's scripted internal assistant want, and why? (Cost note: six small calls; keep the question short and `max_tokens` low.) Afterwards, try the raw-SDK comparison: `uv run python course/02_first_api_call/solution/raw_sdk_demo.py`.

When everything passes, go through [checklist.md](checklist.md).
