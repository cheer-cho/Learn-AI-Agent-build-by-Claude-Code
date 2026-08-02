[🗺 Course Roadmap](../../ROADMAP.html) · [← 03 LangChain](../03_langchain/README.md) · [05 Embeddings →](../05_embeddings/README.md)

# Module 04 — Prompt Engineering

## Objective

Learn to engineer prompts as *code you can test*, not text you retype. You
will build five prompt-builder functions (vague baseline, fully constrained,
one-shot, few-shot, decomposed) around TechCorp policy and support scenarios,
then build a **deterministic rubric** — plain Python, no LLM judge — that
scores any output for constraint following, structure, and unsupported
claims, and use it to *measure* that engineered prompts beat vague ones.

## Estimated difficulty

Beginner-Intermediate. You need the LLM basics from Modules 01–02; every
exercise is string-building plus small scoring functions.

## Prerequisites

- Modules 00–03 completed (environment green, `ChatMessage`/`ChatResult`
  schemas and the mock-vs-live client factory from earlier modules)
- **No API key required** — the whole module runs offline by default

## What you will build

- `starter/prompts.py` completed: `build_vague_prompt()`,
  `build_specific_prompt()`, `build_one_shot_prompt()`,
  `build_few_shot_prompt()`, `build_decomposed_prompt()`, plus three few-shot
  support exemplars you write yourself
- `starter/rubric.py` completed: deterministic scorers
  (`score_word_limit`, `score_required_headings`, `score_sections_present`,
  `score_no_unsupported_claims`) and an aggregator
- A rubric score table comparing all four prompting approaches, printed by
  the comparison script

## Files involved

| File | Role |
|---|---|
| `course/04_prompt_engineering/concepts.md` | Read first — prompt anatomy, shots, decomposition, trade-offs |
| `course/04_prompt_engineering/lab.md` | The four labs plus the evaluation exercise |
| `course/04_prompt_engineering/starter/prompts.py` | Your work: the five prompt builders |
| `course/04_prompt_engineering/starter/rubric.py` | Your work: the deterministic scorers |
| `course/04_prompt_engineering/solution/` | Reference implementation + `run_comparison.py` (peek only after trying) |
| `course/04_prompt_engineering/tests/` | Automated checks for the solution and for your work |
| `course/04_prompt_engineering/checklist.md` | Acceptance criteria |
| `data/privacy/gdpr_summary.md` | Source material for Labs A and D |
| `data/product_support/refund_damaged_products.md` | Source material for Labs B and C |

## Commands

Run these from the repository root:

```bash
uv run python course/04_prompt_engineering/solution/run_comparison.py   # see the score table (offline)
uv run pytest course/04_prompt_engineering -q                           # this module's tests
uv run pytest course/04_prompt_engineering/tests/test_my_work.py -q     # just your completion gate
```

When the checklist passes, tick Module 04 off in
[ROADMAP.html](../../ROADMAP.html) and move on to
[Module 05 — Embeddings](../05_embeddings/README.md).
