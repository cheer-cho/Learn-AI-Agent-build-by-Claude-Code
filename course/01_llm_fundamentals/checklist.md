# Module 01 — Self-Check & Acceptance Criteria

Work through every box honestly before moving on. If one doesn't hold, revisit the file listed next to it.

## Code (acceptance criteria)

- [ ] `uv run pytest course/01_llm_fundamentals -q` passes with **no API key and no network** — 26 passed, 0 skipped.
- [ ] `starter/explorer.py` contains no remaining `TODO` markers (that's what un-skips `tests/test_my_work.py`).
- [ ] `uv run python course/01_llm_fundamentals/starter/explorer.py` runs cleanly and prints: a token count for the apple question, the increased count with 8 noise sentences, both mock responses, and a truncated prompt.
- [ ] My `count_tokens` still works when tiktoken can't load (the fallback tests pass — I didn't just hardcode tiktoken).
- [ ] My `enforce_budget` reject message states the token count, the budget, and what to do about it.

## Understanding (say each answer out loud — see concepts.md if stuck)

- [ ] I can explain what an LLM does at inference time in one sentence (next-token prediction shaped by the input text).
- [ ] I can explain why context differs from training and why retrieval will be needed: the model's weights are frozen and never contained TechCorp's private documents; the only way in is runtime context, the context window can't hold a whole document collection (and pasting it would cost money and degrade quality) — so we must *retrieve* only the relevant passages per question.
- [ ] I can explain why the apple-trivia sentences didn't change the answer (still 16) but were still harmful (token cost, latency, attention dilution).
- [ ] I can explain the difference between input tokens and output tokens, and which typically costs more.
- [ ] I can state two things that are *not* true: "more context is always better" and "the model remembers past chats by itself" — and explain what's actually going on in each case.
- [ ] I know roughly how many tokens a page of English text is (~4 characters per token), and I verified the estimate against real tokenizer output in Task 2.
- [ ] I can name the trade-off triangle I'll be balancing all course: context size vs. cost vs. latency (and past a point, vs. accuracy).

## Looking ahead

- [ ] I understand why Module 02 will show these same token counts on a real API bill, and why Level 2 (Modules 05–08) exists at all.

## Done

- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 01.
