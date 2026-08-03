# Module 09 Lab — Putting a Number on the Assistant

## Scenario

The Module 08 demo went well and now TechCorp leadership is asking the question every demo eventually provokes: *"How good is this assistant — with numbers?"* "It seems to work" is not an answer they can act on, and it is not one you can defend when it starts giving wrong refund windows in production.

Your job is to build the evaluation harness. TechCorp already has a labelled dataset — `data/evaluation/eval_dataset.json`, 33 questions across `answerable`, `paraphrase`, `multi_chunk`, `unanswerable`, `ambiguous`, and `tool_routing` — where each example records the question, the document ids that hold the evidence (`expected_sources`), the fact strings a complete answer must contain (`expected_facts`), and whether the system `should_abstain`. You will implement four metrics and a runner in `starter/eval_lab.py`, then generate a report leadership can read — and read it critically enough to say which category is weakest.

The shared library (`src/techcorp_agent/evaluation/`) already provides `run_evaluation`, `summarize`, and `write_report`; your metric functions must match the permanent copies there, because Modules 17 and 19 re-run this exact evaluation.

## Learning objectives

By the end you can:

- Split a RAG score into retrieval and generation evaluation and explain which layer a failure points at
- Implement `hit_rate_at_k`, `source_accuracy`, `fact_coverage`, and `abstention_correct` with their real boundary semantics
- Run the whole labelled dataset through the pipeline and aggregate per category
- Produce a Markdown report that records its run context
- Read that report honestly — separating meaningful retrieval numbers from placeholder generation numbers under the mock LLM

## Setup

Run commands from the repository root.

- **See the target behavior:** `TECHCORP_OFFLINE=true uv run python course/09_grounding_and_evaluation/solution/run_eval.py`
- **Test:** `uv run pytest course/09_grounding_and_evaluation -q`

Attempt each task before reading the solution.

## Tasks

Open `starter/eval_lab.py`. Each TODO maps to one task below. (The answers are in `solution/eval_lab.py` and in `concepts.md` — reach for them only after trying.)

### Task 1 — Read the dataset schema

Open `data/evaluation/eval_dataset.json`. Nothing to type. Find one example of each category and confirm you can read the four labels the metrics consume: `expected_sources`, `expected_facts`, `should_abstain`, and `category`. Note that `unanswerable` and `ambiguous` examples have empty `expected_sources` and `expected_facts` with `should_abstain: true` — that shape is what makes `hit_rate_at_k` vacuous and hands judgment to `abstention_correct`.

### Task 2 — Implement the four metrics

These are the heart of the lab. Each TODO is one function.

- **`hit_rate_at_k(expected_sources, retrieved_doc_ids, k)`** — RETRIEVAL. If `expected_sources` is empty, return `1.0` (no evidence required, nothing to miss). Otherwise return `1.0` if any expected id appears among the **first `k`** entries of `retrieved_doc_ids` (they are in rank order), else `0.0`.
- **`source_accuracy(expected_sources, cited_sources)`** — GENERATION. If nothing was cited: return `1.0` when `expected_sources` is also empty (a correct abstention cites nothing), else `0.0` (an answer that should cite evidence but doesn't is a failure). Otherwise return (cited sources that were expected) ÷ (cited sources).
- **`fact_coverage(expected_facts, answer_text)`** — GENERATION. Empty `expected_facts` → `1.0`. Otherwise count how many fact strings appear **case-insensitively** inside `answer_text` and divide by `len(expected_facts)`. This is a substring match — a paraphrase scores 0, on purpose.
- **`abstention_correct(should_abstain, abstained)`** — GENERATION. Return `True` exactly when the two flags agree.

### Task 3 — Reason about the boundary cases

Before running anything, predict the answers to these (they are the exact cases the tests check):

- `hit_rate_at_k([], ["doc-a"], k=4)` — hit or miss?
- `source_accuracy([], ["doc-a"])` — the system cited a source for an unanswerable question. Score?
- `fact_coverage(["25 vacation days"], "twenty-five days off")` — coverage?

If your mental model gives the wrong answer here, fix the model before the code. (Answers are in `concepts.md` §3.)

### Task 4 — Wire up the runner

Implement `run_and_report(pipeline, examples, out_path, context)`:

1. Call `run_evaluation(pipeline, examples, k=4)` to score every example (it already skips `tool_routing`).
2. Aggregate with `summarize(results)`.
3. Write the report with `write_report(results, summary, out_path, context or {})`.
4. Return `(results, summary)`.

### Task 5 — Generate the report over the real corpus

Run the reference script to produce the deliverable and prove your mental model matches the numbers:

```bash
TECHCORP_OFFLINE=true uv run python course/09_grounding_and_evaluation/solution/run_eval.py
```

It builds a throwaway index over `data/`, runs the 25 non-`tool_routing` examples, and writes `artifacts/evaluation_report.md`.

### Task 6 — Read the report and find the weakest category

Open `artifacts/evaluation_report.md`. Ignoring the vacuous cases, answer for yourself: **which category has the weakest retrieval, and why?** Look at the per-category `hit rate@k` column, not the overall number — the overall average hides where the system actually fails. (Checkpoint C walks through what you should see. Do not read it until you have formed your own answer.)

## Checkpoints

### Checkpoint A — tests green

```bash
uv run pytest course/09_grounding_and_evaluation -q
```

Once your TODOs are gone, `test_my_work.py` stops skipping and all tests pass. While TODO markers remain, `test_my_work.py` skips — that skip disappearing is your progress bar.

### Checkpoint B — the report exists with its run context

After Task 5, `artifacts/evaluation_report.md` opens with a **Run context** section naming the embedding client and LLM. Under the offline run these are `hash-embedding-384d` and `mock-offline` — and that context is the reason the numbers below mean what they mean.

### Checkpoint C — the real offline numbers

The offline run (hash embeddings + mock LLM) prints this summary, and the report matches it:

```text
embeddings: hash-embedding-384d
llm:        mock-offline
corpus:     13 documents
dataset:    33 examples (8 tool_routing, skipped)

indexed:    67 chunks

overall (n=25): hit rate@4 88% | source accuracy 28% | fact coverage 28% | abstention accuracy 72%
  ambiguous    (n=2): hit rate 100% | abstention 0%
  answerable   (n=10): hit rate 90% | abstention 100%
  multi_chunk  (n=3): hit rate 100% | abstention 100%
  paraphrase   (n=5): hit rate 60% | abstention 100%
  unanswerable (n=5): hit rate 100% | abstention 0%
```

**The weakest real category is `paraphrase` at 60% hit rate.** That is not a bug — it is hash embeddings doing exactly what they do: they match on word overlap, and a paraphrase deliberately avoids the source's words ("denim" for "jeans", "staff time-off guidelines" for "vacation policy"), so the right chunk falls out of the top-k. Module 17's real semantic embeddings are what lift that number, and this baseline is how you will prove they did.

### Checkpoint D — read the generation numbers honestly

Notice the `answerable`, `paraphrase`, and `multi_chunk` categories all show **0% source accuracy and 0% fact coverage**, while `unanswerable` and `ambiguous` show 100%. Do **not** conclude the pipeline is terrible at answering. Under `mock-offline`, the LLM does not actually read the context — it emits a fixed placeholder string that cites nothing and contains none of the expected facts, so every real answer scores 0 on the generation metrics and every abstention scores 1. **The retrieval numbers (`hit rate@k`) are real; the generation numbers are placeholders describing the mock, not any real model.** Run this with a real key in `.env` (drop `TECHCORP_OFFLINE`) and the generation metrics start measuring something. The report's "Reading these numbers honestly" section says this in writing — leadership needs that caveat next to the table.

## Debugging hints

- **`fact_coverage` returns 0 when you expected a hit** → you compared with the wrong case. Lowercase *both* the answer and each fact before `in`. The check is case-insensitive substring, nothing fancier.
- **`source_accuracy([], ["doc-a"])` returns `1.0` in your version** → your empty-`cited_sources` guard fired on the wrong list, or you returned early before checking `expected_sources`. Citing a source when none was expected must score `0.0`.
- **`hit_rate_at_k` counts a doc ranked below `k`** → you searched all of `retrieved_doc_ids` instead of slicing to the first `k`. Rank order matters: slice, then check membership.
- **`test_my_work.py` still skipping after you finished** → a literal `TODO` string is still present in `starter/eval_lab.py`. Delete the resolved marker comments; the gate is literal.
- **Your numbers differ from Checkpoint C** → check the embedding client line at the top of the run. If it says `sentence-transformers/...` instead of `hash-embedding-384d`, you did not force offline mode — the paraphrase hit rate and the whole table shift. Re-run with `TECHCORP_OFFLINE=true`.
- **`run_and_report` returns `None`** → you forgot the final `return results, summary`. `write_report` returns a path, not the tuple the tests assert on.

## Stretch exercise (live only — requires a real key)

The offline generation numbers are placeholders. Make them real: put a key in `.env`, drop `TECHCORP_OFFLINE`, and re-run `solution/run_eval.py`. Now `source_accuracy` and `fact_coverage` measure an actual model reading actual context.

Compare the two reports side by side and answer:

- Which categories' generation numbers moved off 0%, and which expected facts still score low even with a real model? (Hint: the substring check still cannot see a paraphrase of a fact — that is what Module 19's model-based evaluator is for.)
- If you also have `sentence-transformers` available, notice the `paraphrase` hit rate climb above the offline 60% — this is a preview of the Module 17 retrieval upgrade, measured against the exact baseline you just built.

When everything passes, go through [checklist.md](checklist.md).
