# Module 02 Checklist — First LLM API Call

Acceptance criteria — check each item honestly before moving on:

- [ ] I read `concepts.md` and can explain, in my own words: API client vs API key vs base URL vs model identifier.
- [ ] I can state what each role (`system`, `user`, `assistant`) is for and why the system message comes first.
- [ ] `starter/first_call.py` has no remaining `TODO` markers.
- [ ] `uv run python course/02_first_api_call/starter/first_call.py` runs offline end to end and prints: the assistant's content, the safe response inspection, token counts (26 in / 40 out / 66 total with the mock), and an estimated cost of `$0.000186`.
- [ ] My code never assumes the response is a plain string: I guard against empty `choices` and `None` content, and I know where the text actually lives in the response object.
- [ ] `summarize_usage` returns `None` (without crashing) when the provider reports no usage — and I can say *why* usage can be absent.
- [ ] I can compute a request cost by hand from token counts and per-1M-token rates, and my code matches `estimate_cost_usd`.
- [ ] With a deliberately broken key (Checkpoint C) I get an actionable one-paragraph error naming the `.env` setting to fix — no traceback — and I restored `.env` afterwards.
- [ ] I can distinguish the three failure classes — authentication (401), network (no response), and other HTTP status errors — and name the fix for each.
- [ ] No API key appears anywhere in my code; configuration comes only from the environment via `Settings`.
- [ ] `uv run pytest course/02_first_api_call -q` passes with `test_my_work.py` no longer skipped.
- [ ] I read `solution/raw_sdk_demo.py` next to `solution/first_call.py` and can name one thing the adapter buys us and one thing it costs.
- [ ] (Optional, live) I ran the temperature 0 vs 1 stretch and observed the variance difference.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 02.
