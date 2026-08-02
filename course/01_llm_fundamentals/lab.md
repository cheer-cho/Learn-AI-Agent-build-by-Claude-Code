# Lab 01 — Build a Token-and-Context Explorer

## Scenario

Welcome to your first week on TechCorp's AI Platform team. The team is about to build an assistant that answers questions from company documents, and your tech lead has seen too many prototypes die from bloated prompts. Your onboarding task: build a small diagnostic tool that makes token usage *visible* — how big a prompt is, what irrelevant context does to it, and what happens when a prompt blows past a budget. The team will reuse your tool's ideas (token counting, budgets) all the way to production.

## Learning objectives

By the end of this lab you can:

1. Count tokens in any text, with a fallback that works fully offline.
2. Report and compare token counts as context grows.
3. Show, with a controlled experiment, that irrelevant context adds cost without adding correctness.
4. Enforce a token budget with clear reject/truncate behavior.

## Setup

Module 00 already did the heavy lifting. Confirm you're ready:

```bash
uv run python -c "import techcorp_agent; print('ok')"
```

Your working file is `starter/explorer.py`. Run it any time — it always runs, and tells you which tasks remain:

```bash
uv run python course/01_llm_fundamentals/starter/explorer.py
```

Everything below is offline-safe: no API key, no network, no cost.

---

## Task 1 — Implement the token counter

Implement `count_tokens(text)` in `starter/explorer.py`.

- Call the provided `_load_encoding()` helper. If it returns an encoding, return the exact count: the length of `encoding.encode(text)`.
- If it returns `None` (or raises), fall back to the heuristic from concepts.md: about 4 characters per token, never less than 1 → `max(1, len(text) // 4)`.

Why the fallback? `tiktoken` downloads its vocabulary the first time it's used. A learner on a plane (or a CI box with no network) must still be able to run this course — graceful degradation over hard failure.

**Checkpoint 1.** Run the starter. The Task 1 line should now print a real number:

```text
Task 1/2 — token report
  22 tokens in: Sally has 14 apples. Bob has 2 apples. How many apples do they have in total?
```

(22 with tiktoken available; a nearby number like 19 if the heuristic kicked in. Both are correct — one is exact, one is an estimate.)

## Task 2 — Report tokens for a prompt

No new code — this is a measurement exercise with your new counter. Start a Python session:

```bash
uv run python
```

```python
import importlib.util

spec = importlib.util.spec_from_file_location(
    "ex", "course/01_llm_fundamentals/starter/explorer.py"
)
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)

ex.count_tokens("apple")  # expect 1
ex.count_tokens("apples")  # expect 2 — surprised? see concepts.md
ex.count_tokens(ex.APPLE_QUESTION)  # expect 22
```

Write down: does doubling the text length roughly double the tokens? (Try `"apple " * 10` vs `"apple " * 20`.)

## Task 3 — Add configurable irrelevant context

Implement `add_noise(prompt, n_sentences)`.

- Take sentences from the provided `NOISE_SENTENCES` list (all apple trivia — deliberately on-topic but useless).
- Cycle with modulo (`NOISE_SENTENCES[i % len(NOISE_SENTENCES)]`) so `n_sentences` can be any size.
- Join the noise and the prompt with single spaces, **keeping the original prompt intact at the end**.
- `n_sentences <= 0` returns the prompt unchanged.

**Checkpoint 3.** The starter's Task 3 line should show the token count jumping:

```text
Task 3 — noise report
  with 8 noise sentences: 116 tokens
```

That's a ~5× larger prompt for zero additional information — you just measured the cost of noise.

## Task 4 — Compare responses with and without noise

Implement `compare_with_and_without_noise(client, question, n_noise=8)`.

- Call `client.complete([...])` twice: once with a single user `ChatMessage` containing the plain question, once with `add_noise(question, n_noise)`.
- Return both `ChatResult`s as a tuple: `(clean, noisy)`.

The client comes in from outside so the same function works with any client. Offline, `main()` hands you a **scripted** `MockLLMClient` — deterministic, free, and instant. That's also how the tests exercise your function.

**Checkpoint 4.** Running the starter now shows the side-by-side:

```text
Task 4 — compare responses
  clean: 'Sally has 14 apples and Bob has 2, so together they have 16 apples.'
  noisy: 'There are many apple facts here. Counting the varieties mentioned ...'
```

Look at the `usage` on each result too (`clean.usage.input_tokens` vs `noisy.usage.input_tokens`): same question, same correct answer available, several times the input cost.

**Optional live comparison** (requires `OPENAI_API_KEY` in `.env`; spends a fraction of a cent): with a key configured, `main()` automatically uses the real client via `get_llm_client()`. Try `n_noise=8`, then crank it up (see the stretch exercise) and watch whether the live model's answer stays clean or starts hedging about apple varieties.

## Task 5 — Enforce a token budget

Implement `enforce_budget(text, max_tokens, mode="reject")`.

- Unknown modes → `ValueError` immediately (only `"reject"` and `"truncate"` exist).
- Within budget → return `text` unchanged, either mode.
- `mode="reject"` and over budget → raise `ValueError` whose message states the actual token count, the budget, and what the caller can do about it. "Input too long" is not acceptable; error messages are UI.
- `mode="truncate"` and over budget → return text that fits: with the tiktoken encoding, `encoding.decode(encoding.encode(text)[:max_tokens])`; without it, keep the first `max_tokens * 4` characters.

**Checkpoint 5.** The starter's Task 5 line prints a truncated prompt, and the full demo in `solution/explorer.py` shows both modes. Note what truncation kept: the *noise at the front* — the actual question got cut off. Blind truncation is a blunt instrument; choosing *what* to keep is the retrieval problem (Level 2).

## Final check

```bash
uv run pytest course/01_llm_fundamentals/tests/test_my_work.py -q
```

All tests should pass (they stop auto-skipping once no `TODO` remains in `starter/explorer.py`). Then run the whole module suite:

```bash
uv run pytest course/01_llm_fundamentals -q
```

Expected: `26 passed` (13 for the reference solution, 13 for yours).

---

## Debugging hints

- **`ModuleNotFoundError: techcorp_agent`** — run commands from the repository root, and re-run `uv sync` if needed.
- **Tests still skipping after you finished** — the skip triggers on the literal string `TODO` anywhere in `starter/*.py`. Delete the marker comments, not just the `raise` lines.
- **`count_tokens` returns 0** — the heuristic must be wrapped in `max(1, ...)`; a 2-character string is still ≥ 1 token.
- **`test_cycles_past_list_length` fails** — you're probably indexing `NOISE_SENTENCES[i]` directly; use `i % len(NOISE_SENTENCES)`.
- **`test_scripted_mock_records_two_calls` fails on call order** — make the *clean* call first, then the noisy one; the scripted mock returns responses in order.
- **`test_truncate_fits_budget` fails by 1 token** — decode-then-count can disagree with slicing if you truncate characters while tiktoken is available. When you have the encoding, truncate in *token* space (`encode → slice → decode`), not character space.
- **Your reject message fails the test** — it must contain the word "budget" and at least one number. Say what happened and what to do next.
- **Live mode surprises** — no key or `TECHCORP_OFFLINE=true` means the mock client; that's by design. Force offline any time with `TECHCORP_OFFLINE=true uv run python ...`.

## Stretch exercise

**How much noise breaks a 1k budget?** Write a small loop (a scratch script, or extend `main()`) that increases `n_sentences` until `count_tokens(add_noise(APPLE_QUESTION, n))` exceeds a 1,000-token budget, and print the first `n` that does it, e.g.:

```text
n= 60  ->  733 tokens
n= 70  ->  853 tokens
n= 83  -> 1005 tokens  <-- budget of 1000 first exceeded here
```

Then estimate (using `estimate_cost_usd` from `techcorp_agent.costs` with the default rates in `Settings`) how much money that noise would waste per 1,000 requests. Bonus: how many *tokens per noise sentence* is that on average, and does the number match the ~4-chars-per-token rule?

When everything passes, finish with [checklist.md](checklist.md).
