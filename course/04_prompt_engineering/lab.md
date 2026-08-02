# Module 04 Lab — Prompt Engineering

## Scenario

TechCorp's support and legal teams keep getting inconsistent drafts out of
the LLM: policies with random lengths and headings, support replies that
ignore the escalation rule, compliance reviews that are one unusable
paragraph. Your job this week: turn prompting into engineering. You will
build five prompt-builder functions and a deterministic rubric, then prove —
with scores, not vibes — that the engineered prompts win.

## Learning objectives

By the end you can:

1. Convert a vague request into a prompt with role, context, constraints, and
   output format.
2. Use one-shot prompting to transfer a document's structure to a new topic.
3. Use few-shot prompting to transfer tone, format, and business rules.
4. Decompose a complex review into five checkable, labeled outputs.
5. Score prompt outputs with deterministic code and compare approaches.

## Setup

```bash
uv sync                                  # if you haven't already (Module 00)
uv run pytest course/04_prompt_engineering -q   # baseline: solution tests pass, yours skip
```

You will edit exactly two files:

- `course/04_prompt_engineering/starter/prompts.py`
- `course/04_prompt_engineering/starter/rubric.py`

Everything runs offline. No API key is needed for any checkpoint.

> **Live mode makes this real.** The comparison script scores *curated* canned
> outputs from the scripted `MockLLMClient`, so the contrast is guaranteed and
> free. If you set `OPENAI_API_KEY` in `.env`, you can swap the mock for
> `get_llm_client()` (see the stretch exercise) and watch a real model respond
> to your actual prompts — the scores become genuinely yours, and genuinely
> variable. Recommended once, after everything passes offline.

A useful way to eyeball any prompt while you work:

```bash
uv run python -c "
from pathlib import Path
from techcorp_agent.course_utils import import_from_path
p = import_from_path('p', Path('course/04_prompt_engineering/starter/prompts.py'))
print(p.build_vague_prompt())
"
```

---

## Lab A — Vague vs specific

**Scenario.** Legal asks for "a data retention policy for our European
customers". A teammate sends the model `Write a policy.` and forwards
whatever comes back. You will build both that baseline and the version Legal
actually needs, and score the difference.

**Objectives.** Implement `build_vague_prompt()` and
`build_specific_prompt(constraints)`; understand why each constraint earns
its place.

**Steps.**

1. Read `data/privacy/gdpr_summary.md` — this is the GDPR context your policy
   lives in (note the customer rights and the storage-limitation spirit).
2. In `starter/prompts.py`, complete `build_vague_prompt()` — it returns
   exactly `Write a policy.` That's the control group; don't improve it.
3. Complete `build_specific_prompt(constraints)`. Using the
   `SPECIFIC_POLICY_CONSTRAINTS` dict, your prompt must contain, verbatim:
   - a role instruction (a TechCorp policy writer),
   - the audience: `European customers`,
   - the literal phrase `200-word` (build it from `constraints["word_limit"]`),
   - the regulation name `GDPR`,
   - the literal phrase `30-day` (from `constraints["retention_days"]`),
   - all four headings: `Purpose`, `Scope`, `Retention`, `Your Rights`,
   - a "do not invent facts not given here" instruction.
4. Print both prompts side by side (snippet above) and ask yourself, for each
   line of the specific prompt: *which failure does this line prevent?*

**Checkpoint A.** Run:

```bash
uv run pytest course/04_prompt_engineering/tests/test_my_work.py -q -k "vague or specific"
```

Expected observable output once `prompts.py` has no TODO markers left:
the two Lab A tests either pass, or (while other TODOs remain anywhere in
`starter/`) everything still shows `s` (skipped). All tests in this module
unskip together when the last TODO marker disappears from `starter/`, so
finish both files before expecting green.

**Debugging hints.**

- `AssertionError` on `"200-word"` or `"30-day"`: build the phrase with an
  f-string — `f"{constraints['word_limit']}-word"` — don't hard-code numbers
  or write "200 words" (no hyphen fails the verbatim check).
- Missing heading failures: include each heading string exactly, e.g. in a
  "use exactly these headings" line joined with `/`.
- Tests still skipping after you finished? Search both starter files for the
  string `TODO` — any leftover marker (even in a comment) keeps the skip on.

---

## Lab B — One-shot structure transfer

**Scenario.** HR loves the *shape* of the refund policy in
`data/product_support/refund_damaged_products.md` — tight scope, options,
requirements, timing, escalation — and wants the remote-work policy "to look
exactly like that". Describing a structure in words is clumsy; showing one
example is precise.

**Objectives.** Implement `build_one_shot_prompt(example, target)`; observe
that structure transfers even when the topic changes completely.

**Steps.**

1. Read `data/product_support/refund_damaged_products.md`, then look at
   `EXAMPLE_REFUND_POLICY` in `starter/prompts.py` — a condensed adaptation
   with five headings (Scope / Your Options / What We Need From You / Timing
   / Escalation). This is your one "shot".
2. Complete `build_one_shot_prompt(example, target)`. The prompt must:
   - include the full `example` text (delimit it clearly, e.g.
     `=== EXAMPLE POLICY ===` fences),
   - name the `target` (e.g. `remote-work policy for TechCorp employees`),
   - instruct the model to reuse the example's headings and their order,
   - instruct it *not* to copy the example's facts — structure only.
3. Print the prompt. Confirm a stranger could tell exactly which parts are
   the example and which are the request.

**Checkpoint B.**

```bash
uv run pytest course/04_prompt_engineering/tests/test_my_work.py -q -k one_shot
```

Expected observable output: `test_one_shot_prompt_contains_example_and_target`
passes — the full example and the target subject both appear in your prompt.

**Debugging hints.**

- Test fails on `example in prompt`: you must embed the example *unchanged* —
  no `.strip()`, no re-indenting, no truncation.
- If the model (in live mode) copies refund facts into the remote-work
  policy, your "reuse structure, not facts" instruction is missing or buried
  below the example — put instructions after the example too.

---

## Lab C — Few-shot support style

**Scenario.** New support agents (human and AI) keep answering customers with
curt, format-free replies and forgetting that anything over $500 needs a
Tier 2 manager. Support's house style is easier to *show* than to describe —
so you'll show it three times.

**Objectives.** Write three exemplar responses; implement
`build_few_shot_prompt(examples, question)`.

**Steps.**

1. Replace the three `TODO` placeholders in `FEW_SHOT_EXEMPLARS` with three
   full support responses you write yourself. Base their facts on
   `data/product_support/refund_damaged_products.md`, and make every exemplar
   demonstrate all three house rules:
   - **empathetic tone** — a personal opening that acknowledges the problem
     (e.g. "Hi Priya, thanks for reaching out — I'm sorry your…"),
   - **specific format** — the same labeled skeleton in each (e.g.
     `What happened:` / `What we'll do:` / `Next steps:`), and a sign-off,
   - **the escalation rule** — each exemplar states whether the amount is
     under or over $500 and what that means (Tier 2 manager, up to 48 hours).
   Vary the customer and the problem across the three, keep the skeleton
   identical — the *variation shows the model what is fixed*.
2. Complete `build_few_shot_prompt(examples, question)`: a role line, the
   house rules in one sentence, each example in a numbered fence
   (`=== EXAMPLE RESPONSE 1 ===` …), then the new customer message, then
   "respond in the same style".
3. Print the full prompt once. Notice its size — you'll account for that cost
   in the evaluation exercise.

**Checkpoint C.**

```bash
uv run pytest course/04_prompt_engineering/tests/test_my_work.py -q -k few_shot
```

Expected observable output:
`test_few_shot_prompt_contains_all_exemplars_and_question` passes — all three
exemplars and the customer question appear in the prompt.

**Debugging hints.**

- Exemplar-containment failures usually come from mutating the exemplar
  strings while joining (e.g. `.strip()` on each). Join them untouched.
- Keep the word `TODO` out of your finished exemplars — any occurrence keeps
  the whole test file skipped.
- Quality self-check (the tests can't grade prose): cover one exemplar, read
  the other two, and see if you can predict its skeleton. If not, the shots
  disagree and the model will too.

---

## Lab D — Decomposed policy review

**Scenario.** Legal wants the draft retention policy reviewed against GDPR.
One-blob reviews come back as a paragraph of mixed judgment nobody can act
on. You'll force the review through five labeled steps so every conclusion
traces to evidence.

**Objectives.** Implement `build_decomposed_prompt(policy_text)`; practice
requesting explicit intermediate outputs instead of hidden reasoning.

**Steps.**

1. Look at `DECOMPOSED_SECTIONS` in `starter/prompts.py`:
   `Applicable Requirements`, `Current-Policy Observations`, `Gaps`,
   `Recommendations`, `Implementation Steps`.
2. Complete `build_decomposed_prompt(policy_text)`. The prompt must:
   - set the role (TechCorp compliance analyst reviewing against GDPR),
   - name all five sections and require each under its own numbered heading,
   - define each section's job — requirements are a list; observations are
     neutral quotes/paraphrases of the policy text (no judgment yet); each
     gap must name the requirement *and* the observation it conflicts with
     (a structured rationale, traceable to evidence); one recommendation per
     gap; implementation steps as an ordered task list,
   - restrict evidence to the included `policy_text` ("do not invent policy
     details not written here"),
   - embed `policy_text` inside clear fences.
3. Note what you did **not** ask for: the model's private hidden reasoning.
   Every one of the five sections is a legitimate output you can check.

**Checkpoint D.**

```bash
uv run pytest course/04_prompt_engineering/tests/test_my_work.py -q -k decomposed
```

Expected observable output: `test_decomposed_prompt_names_all_five_sections`
passes — the policy text and all five labels appear in your prompt.

**Debugging hints.**

- Label mismatches are almost always hyphens/plurals: it is
  `Current-Policy Observations` (hyphen, plural) and `Implementation Steps`
  (plural). Build the list from `DECOMPOSED_SECTIONS` instead of retyping.
- In live mode, if sections bleed into each other, number the headings and
  add "output nothing outside these five sections".

---

## Evaluation exercise — score every approach with the rubric

**Scenario.** Now make the comparisons measurable. The rubric is
deterministic code — the same output always gets the same score, and you can
point at the exact check behind every number.

**Steps.**

1. In `starter/rubric.py`, complete the scorers (all return floats in
   `[0.0, 1.0]`):
   - `score_word_limit(text, limit)` — 1.0 iff non-empty and ≤ `limit` words
     (**constraint following**),
   - `score_required_headings(text, headings)` — fraction of required
     headings present, case-insensitive (**structure**),
   - `score_sections_present(text, labels)` — same mechanic, used for Lab D's
     five sections (**structure/consistency** — run it on repeated outputs in
     live mode to see consistency directly),
   - `score_no_unsupported_claims(text, context)` — fraction of numbers in
     the output that also appear in the provided context. This is an honest
     **approximation** of "no unsupported claims" for a small controlled
     case: numbers are the easiest facts to fabricate and the easiest to
     check; prose claims are not checked, so 1.0 is not proof of grounding,
   - `score_output(...)` and `total_score(...)` — aggregate only the criteria
     that apply to a given lab (that's the **relevance** guard: a lab is
     scored on what its prompt actually promised).
2. Run the reference comparison and read the table:

   ```bash
   uv run python course/04_prompt_engineering/solution/run_comparison.py
   ```

3. For each lab, identify which rubric row exposes the weak output's failure,
   and check it against the canned texts in `solution/run_comparison.py`.
4. Write (for yourself) one sentence per lab: what did the engineered prompt
   buy, and what did it cost in prompt tokens? Lab C should sting a little —
   three exemplars in *every* request is the price of consistency.

**Checkpoint E.** Expected observable output from step 2 — four tables in
this shape, weak column visibly below strong (your exact fractions for the
weak side may differ from this excerpt):

```text
=== Lab A — vague vs specific =================================
criterion                       weak (vague)     strong (specific)
------------------------------------------------------------------
word_limit                              0.00                  1.00
headings                                0.00                  1.00
supported_claims                        0.00                  1.00
TOTAL                                   0.00                  1.00
```

Then the full gate:

```bash
uv run pytest course/04_prompt_engineering -q
```

Expected observable output: all tests pass, none skipped (a plain line of
dots, e.g. `......................`).

**Debugging hints.**

- `mixed == 0.5` failing in the claims test: score the *fraction* of numbers
  supported, not all-or-nothing, and return 1.0 when the text has no numbers.
- Headings fraction off: compare case-insensitively (`text.lower()`), and
  divide by `len(headings)`, not by the number found.
- `score_output` key errors: use exactly the keys `"word_limit"`,
  `"headings"`, `"sections"`, `"supported_claims"`, and only for arguments
  that are not `None`.

---

## Stretch exercise

1. **Go live.** Copy `solution/run_comparison.py` into your scratch space and
   replace the scripted `MockLLMClient(responses=[...])` with
   `get_llm_client()` from `techcorp_agent.llm.factory` (requires
   `OPENAI_API_KEY` in `.env`). Send your *own* starter prompts, score the
   real outputs, and compare with the canned table. Run the few-shot lab
   three times: does `score_sections_present` hold at 1.0 every time? That's
   the consistency few-shot buys.
2. **Break the rubric on purpose.** Write an output that scores a perfect
   1.0 across the board yet is a terrible policy (right headings, right
   numbers, nonsense prose). Now you know precisely what deterministic
   rubrics don't see — carry that skepticism to Module 09 (grounding) and
   Module 19 (evaluation).
