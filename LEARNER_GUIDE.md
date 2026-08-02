# Learner Guide

How to get the most out of this course.

## The loop for every module

1. Open the module's `README.md` (each links back to [ROADMAP.html](ROADMAP.html)).
2. Read `concepts.md` — it introduces every term before the lab uses it.
3. Work through `lab.md` in the module's `starter/` directory. Starter code
   runs but has meaningful `# TODO:` gaps — that's where you learn.
4. Run the module's tests (each README gives the exact command).
5. Compare with `solution/` **after** your attempt, not instead of it.
6. Complete `checklist.md`, then tick the module off in the roadmap.

## Offline vs live mode

- **Offline (default)**: no API key; deterministic mock LLM and hash
  embeddings. All plumbing, tests, and most labs work. Free.
- **Live**: set `OPENAI_API_KEY` (and optionally `OPENAI_BASE_URL`,
  `OPENAI_MODEL`) in `.env`. Labs that compare real model behavior are far
  more interesting live. Cost guidance appears in each module; the course
  defaults (`MAX_OUTPUT_TOKENS`, cost tracking from Module 02) keep spend low —
  typically well under a few dollars for the whole course.
- Embeddings are **always free**: sentence-transformers runs locally
  (one ~90 MB download). `TECHCORP_OFFLINE=true` skips even that.

## When you're stuck

- Every lab has **Debugging hints** near the step where things usually break.
- `make verify` diagnoses environment problems.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) covers the common failures.
- Reading the module's tests is a legitimate strategy — they encode exactly
  what "working" means.

## Pacing

Levels are natural stopping points. Modules within a level build on each
other; don't skip within a level. If you already know a topic, run the
module's tests against your own from-scratch attempt and move on when green.
