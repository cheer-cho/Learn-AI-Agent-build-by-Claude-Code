# Module 08 Lab — Build TechCorp's RAG Pipeline

## Scenario

TechCorp's employees keep asking the same policy questions — dress code, remote-work limits, refund rules — and the answers all live in documents you already indexed in Module 07. Your team lead wants a pipeline that reads those documents *for* the employee and returns a direct, cited answer. But there is a hard requirement: it must **never** make policy up. If the documents don't cover the question, it says so, plainly, rather than guessing. A wrong answer about a refund is a real problem; "not in the documents" is not.

You will implement `starter/my_rag.py` — a `MyRAGPipeline` class with the same contract as the shared `techcorp_agent.rag.RAGPipeline`. The grounding rules (`SYSTEM_PROMPT`, `ABSTENTION_TEXT`) and the `SOURCES:` regex are prewritten; your job is to wire retrieval, augmentation, generation, and the safety guardrails together correctly.

## Learning objectives

By the end you can:

- Retrieve chunks from a vector store with a similarity threshold.
- Render retrieved chunks into a grounded prompt that names each source.
- Assemble a system + user conversation that carries the rules, the evidence, and the question.
- Parse a model reply into a clean answer plus a list of source ids.
- Filter hallucinated citations and detect abstention.
- Abstain *before* calling the model when nothing relevant was retrieved.

## Setup

```bash
uv sync                      # if you haven't already
```

Run commands from the repository root. Everything runs offline — no API key needed.

- **Run your work:** `uv run python course/08_rag/starter/my_rag.py`
- **Test:** `uv run pytest course/08_rag -q`
- **Peek at the target behavior anytime:** `uv run python course/08_rag/solution/my_rag.py` and `TECHCORP_OFFLINE=true uv run python course/08_rag/solution/demo.py` (but attempt each task before reading solution code).

The starter's `main()` is a prewritten walkthrough over a fixed three-chunk mini corpus with a scripted mock LLM, so every checkpoint below is exact and reproducible. Each unimplemented step raises `NotImplementedError` with a pointer to its task, so the script always runs as far as your progress.

## Tasks

Open `starter/my_rag.py`. The TODOs are numbered to match the tasks; the pipeline reads top to bottom, so implement them in the order below (which walks the data through the pipeline).

### Task 1 — `retrieve(self, question)`

Vector-search the store, keeping only chunks above the threshold. Query `self._store` with the question, passing `top_k=self._top_k` and `min_score=self._min_score`, and return the result (a `list[RetrievedChunk]`).

**Checkpoint 1** — run `uv run python course/08_rag/starter/my_rag.py`. Step 1 should print:

```text
--- Step 1: retrieve ---
question: Can I wear jeans at headquarters?
  hr-dress-code            score=0.241
```

Only `hr-dress-code` clears the `0.10` threshold the demo uses; the other two mini-corpus chunks score too low on word overlap and are filtered out. Then the script stops at the next `NotImplementedError` — expected, keep going.

*Hint:* `store.query` already applies `min_score` for you. Don't re-filter or sort by hand — just pass the arguments through and return what you get.

### Task 2 — `build_context_block(chunks)`

Render each retrieved chunk as a source-labelled section. For each `retrieved` chunk, the `doc_id`, `doc_title`, and `text` live on `retrieved.chunk`. Produce a section of the form:

```text
[source: <doc_id>] <doc_title>
<chunk text>
```

Join the sections with `"\n\n---\n\n"` and return the string.

**Checkpoint 2** — Step 2 now prints:

```text
--- Step 2: context block ---
[source: hr-dress-code] Dress Code Policy
Business casual is the default dress code. Jeans are allowed at headquarters.
```

*Hint:* the `[source: ...]` prefix is not decoration — the tests assert on the exact substring `[source: test-dress-code]` appearing in the prompt. Match the format precisely, including the space after the colon.

### Task 3 — `build_messages(self, question, chunks)`

Assemble the grounded conversation. Return a list of two `ChatMessage`s:

1. a `system` message whose content is `SYSTEM_PROMPT`;
2. a `user` message of the form:

   ```text
   Context documents:

   <build_context_block(chunks)>

   Question: <question>
   ```

**Checkpoint 3** — Step 3 prints the first line of each message:

```text
--- Step 3: grounded messages ---
[system] You are TechCorp's internal knowledge assistant.
[user  ] Context documents:
```

*Hint:* the user message must **end** with `Question: <question>` (the tests check `user.content.rstrip().endswith("Question: ...")`). Put the question last, after the context — not before it.

### Task 5 — `parse_answer(raw)`

(Task 4 is the generate call in `answer()`; you'll do it together with 6–8 below. Parsing comes first because `answer()` calls it.)

Split the model reply into `(answer_text, source_ids)`:

- Find the `SOURCES:` line with `_SOURCES_RE.search(raw)` (prewritten; `match.group(1)` is everything after the colon).
- **No match** → return `(raw.strip(), [])`.
- Otherwise the answer is everything *before* the match, stripped: `raw[: match.start()].strip()`.
- If the sources field is empty or `"none"` (any case) → return the answer with `[]`.
- Otherwise split on commas, strip whitespace off each id, drop empties, and de-duplicate while preserving order.

*Hint for de-duplication:* `list(dict.fromkeys(items))` keeps first-seen order and drops repeats in one step.

### Tasks 4, 6, 7, 8 — `answer(self, question)`

This is the whole pipeline. Implement it in this order:

- **Task 8 (retrieve-then-guard, first):** call `self.retrieve(question)`. If it came back **empty**, return `RAGAnswer(answer=ABSTENTION_TEXT, sources=[], abstained=True)` immediately — **do not call the LLM**. No evidence means no grounded answer, and skipping the call saves a request.
- **Task 4 (generate):** otherwise call `self._llm.complete(self.build_messages(question, chunks))` and pass `result.content` to `parse_answer(...)` to get `answer_text` and `sources`.
- **Task 6 (filter citations):** build `supplied_ids = {retrieved.chunk.doc_id for retrieved in chunks}` and keep only sources that are in it. The model may cite documents it never saw; those must be dropped.
- **Task 7 (detect abstention):** set `abstained = ABSTENTION_TEXT.lower() in answer_text.lower()`. If abstained, force `sources = []`. Return `RAGAnswer(answer=answer_text, sources=sources, abstained=abstained)`.

**Checkpoint 4** — Steps 4–8 now run. The full offline output (deterministic — yours must match):

```text
--- Steps 4-7: grounded answer ---
answer:    Yes — jeans are allowed at headquarters.
sources:   ['hr-dress-code']
abstained: False

--- Hallucinated citation is filtered ---
sources:   ['hr-dress-code']  (fashion-blog-2026 was never supplied)

--- Step 8: nothing retrieved → abstain without an LLM call ---
answer:    I do not have enough information in the provided TechCorp documents to answer that question.
sources:   []
abstained: True
LLM calls: 0

--- Final: your pipeline vs the shared library ---
identical RAGAnswer from both pipelines: True
```

*Hints for the failure-prone parts:*

- `fashion-blog-2026` disappearing from the second block is Task 6 working. If it survives, you filtered against the wrong set (or not at all) — the keeper set is the *retrieved* chunks' `doc_id`s, not the model's claimed sources.
- `LLM calls: 0` in Step 8 is Task 8 working. If it prints `1`, your empty-retrieval guard runs *after* the `complete()` call instead of before it. The guard must return before any model call.
- The abstention text must match `ABSTENTION_TEXT` exactly. It already does if you imported it and didn't retype it — that's why the starter imports it for you.

### Final task — swap in the shared library

The last block of `main()` is prewritten: it runs the *same* scripted question through your `MyRAGPipeline` and through `techcorp_agent.rag.RAGPipeline` and compares the two `RAGAnswer`s. When it prints `identical RAGAnswer from both pipelines: True`, you have rebuilt the library's contract exactly. That equality is the whole point of the module — your pipeline and the shared one are behavior-identical.

## What the six test scenarios check

`tests/test_my_work.py` runs the same six scenarios the reference solution is tested against (over a small controlled corpus written to a temp directory so hash-embedding retrieval is deterministic). Knowing what each one *proves* tells you what your pipeline must get right:

1. **Fully answerable** — a question the documents answer outright. Checks the answer is grounded, `abstained is False`, the single correct source is credited, the `SOURCES:` line is stripped off the answer, and the prompt carried both the rules (`ONLY from the context documents`) and the evidence (`[source: test-dress-code]`), ending in `Question: ...`.
2. **Partially answerable** — the documents answer *part* of a two-part question. Checks the pipeline cites what exists (`test-vacation`) and passes through the model's acknowledgement of the gap (`do not say`) without inventing the missing half.
3. **Unanswerable** — a question nothing covers (a `min_score=0.999` threshold guarantees empty retrieval). Checks it abstains, returns exactly `ABSTENTION_TEXT`, no sources, and — critically — makes **zero** LLM calls.
4. **Conflicting chunks** — two retrieved documents disagree (restocking fee vs. full refund for damaged goods). Checks *both* are retrieved and supplied to the prompt, and both are credited as sources; the pipeline surfaces the conflict rather than picking one.
5. **Low-similarity retrieval** — an off-topic question that only weakly overlaps the corpus, run with `min_score=0.5`. Checks the weak matches are rejected by the threshold, so it abstains with zero LLM calls. This is the threshold doing its job.
6. **Multi-chunk question** — one question that needs two different documents (remote-work days *and* another-country rules). Checks both sources reach the prompt and both are credited — a single answer spanning multiple chunks.

Two further guardrail tests round it out: a **hallucinated source** (`wikipedia-dress-codes`) must be filtered out, and a **model-side abstention** must be detected and carry no sources.

## The full-corpus demo

To see the pipeline on the *real* TechCorp documents rather than the mini corpus, run:

```bash
TECHCORP_OFFLINE=true uv run python course/08_rag/solution/demo.py
```

It indexes all 13 documents and runs the six scenarios end to end. Watch scenario 5 in particular — at `min_score=0.30` the iguana question retrieves `[]` and abstains:

```text
=== 5. Low-similarity retrieval (min_score=0.3) ===
question:  Does TechCorp allow pet iguanas in offices?
retrieved: []
answer:    I do not have enough information in the provided TechCorp documents to answer that question.
sources:   []
abstained: True
```

## Checkpoint — tests green

```bash
uv run pytest course/08_rag -q
```

Expected once your TODOs are gone: all tests pass. While TODO markers remain in `starter/my_rag.py`, `test_my_work.py` skips — that skip disappearing is your progress bar.

## Debugging hints

- **`test_my_work.py` still skipping after you finished** → a `TODO` string is still present somewhere in `starter/my_rag.py`. The gate is literal; delete the marker comments you resolved.
- **`SOURCES:` text leaking into `result.answer`** → `parse_answer` isn't splitting on the match. The answer is `raw[: match.start()]`, everything *before* the SOURCES line, stripped.
- **A hallucinated id survives in `result.sources`** → Task 6. Filter against `{r.chunk.doc_id for r in chunks}`, the ids you actually supplied — not against the model's own list.
- **`LLM calls` is 1 when it should be 0** → your empty-retrieval guard runs after `complete()`. Move the `if not chunks:` return to the top of `answer()`, before any model call.
- **An abstaining reply still lists sources** → Task 7. After computing `abstained`, force `sources = []` when it's true.
- **`ValidationError` constructing `ChatMessage`** → the `role` must be exactly `system` or `user`.
- **`ModuleNotFoundError: techcorp_agent`** → run from the repository root with `uv run`, not bare `python` inside the module directory.

## Stretch exercise — the threshold dial

`min_score` is the knob between answering and abstaining. Make it visible. In a scratch copy (or by editing the demo's `min_score` values), take scenario 5's iguana question and lower the threshold from `0.30` toward `0.0`. Watch coincidental word-overlap chunks start clearing the bar and being retrieved — the pipeline stops abstaining and begins feeding weak "evidence" to the model. Then push a *good* question's threshold up toward `1.0` and watch it start abstaining on a question it could have answered.

Then decide: where should TechCorp set `min_score` for an internal policy assistant, and what does each direction cost? (Recall the trade-off from [concepts.md](concepts.md): higher = more abstentions but stronger grounding; lower = more answers but weaker evidence.)

When everything passes, go through [checklist.md](checklist.md).
