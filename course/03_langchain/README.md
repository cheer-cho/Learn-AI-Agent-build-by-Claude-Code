[🗺 Course Roadmap](../../ROADMAP.html) · [← 02 First API Call](../02_first_api_call/README.md) · [04 Prompt Engineering →](../04_prompt_engineering/README.md)

# Module 03 — LangChain Fundamentals

## Objective

In Module 02 you wrote your own small adapter around a provider SDK. In this
module you meet LangChain — a framework that ships the same idea (and much
more) as a library — and learn exactly what it saves you, what it hides, and
when each level of abstraction is the right call. You will make the same LLM
request through both stacks, build a reusable prompt template, get typed
Pydantic objects out of a model, and compose prompt → model → parser into a
single runnable chain.

## Difficulty

Beginner–Intermediate

## Prerequisites

- Module 00 complete (repo installed, `uv run pytest tests -q` green)
- Module 02 complete (you understand messages, roles, and `techcorp_agent.llm`)
- No API key required — every lab runs offline against a scripted fake model.
  With `OPENAI_API_KEY` in `.env`, the same code talks to a real provider.

## What you will build

- **Lab A — SDK versus LangChain**: the same TechCorp question answered twice —
  once through our Module 02 adapter, once through LangChain's chat-model
  interface — plus your own comparison table of the two stacks.
- **Lab B — Prompt template**: a reusable `ChatPromptTemplate` for drafting
  TechCorp policy documents, parameterized by `policy_type`, `audience`,
  `length`, `constraints`, and `output_format`.
- **Lab C — Structured output**: a `PolicySummary` Pydantic model returned from
  the model via `PydanticOutputParser` — validated fields, not raw strings.
- **Lab D — Chain composition**: `prompt | model | parser` as one runnable that
  takes a dict of five variables and returns a typed `PolicySummary`.

## Files involved

| File | Role |
| --- | --- |
| `concepts.md` | Why abstractions exist; LLM vs agent; adapters at two altitudes |
| `lab.md` | The four labs, step by step |
| `starter/langchain_labs.py` | Your workspace — `get_lc_model` is pre-built, the rest is `# TODO` |
| `solution/langchain_labs.py` | Reference implementation with a demo `main()` per lab |
| `tests/test_solution.py` | Always-green tests for the reference solution |
| `tests/test_my_work.py` | Your completion gate — auto-skips until you remove the TODOs |
| `checklist.md` | Self-check before moving on |
| `src/techcorp_agent/llm/` | Module 02's adapter, reused for Lab A's raw path |

## Commands

```bash
# Watch the finished module run (fully offline):
uv run python course/03_langchain/solution/langchain_labs.py

# Work on the labs, re-running as you go:
uv run python course/03_langchain/starter/langchain_labs.py

# Verify the module (solution tests always run; yours unlock as you finish):
uv run pytest course/03_langchain -q

# Optional, spends credits — native structured output on a real provider:
uv run pytest course/03_langchain -m live
```
