# Lab — LangChain Fundamentals

All four labs live in one file: `starter/langchain_labs.py`. Read
`concepts.md` first, then work through the labs in order — each one builds on
the previous.

**Before you start**, read the pre-built helper `get_lc_model()` at the top of
the starter file. Every lab depends on it. It returns:

- a `FakeListChatModel` replaying `scripted_responses` when you pass them
  (deterministic — this is how the tests drive your code),
- a fake model with one canned reply when you are offline with no script,
- a real `ChatOpenAI` when `OPENAI_API_KEY` is set in `.env`.

Re-run your work after every step — the file always runs, even half-finished:

```bash
uv run python course/03_langchain/starter/langchain_labs.py
uv run pytest course/03_langchain/tests/test_my_work.py -q
```

---

## Lab A — SDK versus LangChain

### Scenario

TechCorp's platform team is debating whether the assistant should keep the
hand-rolled adapter from Module 02 or adopt LangChain before the codebase
grows. You settle it the engineering way: implement the same request on both
stacks and compare them with evidence.

### Objectives

- Send the same question through `techcorp_agent.llm` (Module 02 style) and
  through LangChain's chat-model interface.
- Verify both stacks produce identical output for identical scripted input.
- Form your own judgment about what the framework saves and hides.

### Steps

1. Implement `ask_raw_sdk(question, client)`: build a two-message conversation
   with `ChatMessage` (a `"system"` message using `SYSTEM_PROMPT`, a `"user"`
   message with the question), call `client.complete(...)`, return the
   result's `.content`. This is exactly the Module 02 pattern.
2. Implement `ask_langchain(question, model)`: call `model.invoke([...])` with
   a `SystemMessage(SYSTEM_PROMPT)` and a `HumanMessage(question)`; the reply
   is an `AIMessage` — return its `.text` property.
3. Run the starter file. `main_lab_a` feeds both paths the same scripted reply
   through `MockLLMClient` and `get_lc_model(scripted_responses=...)`.
4. Fill in this comparison table **in your own words** (keep it — the
   checklist asks for it):

   | Dimension | Raw SDK path (Module 02) | LangChain path |
   | --- | --- | --- |
   | Lines of application code | | |
   | Portability to another provider | | |
   | Visibility of provider-specific features | | |
   | Error handling (who translates errors?) | | |
   | Testability offline | | |

### Checkpoints

- [ ] `main_lab_a` prints both replies and `identical : True`.
- [ ] `test_lab_a_both_paths_return_the_same_scripted_content` passes.
- [ ] Your table has all five rows filled in.

### Debugging hints

- `AttributeError: 'AIMessage' object has no attribute 'content'`-style
  confusion: the raw path returns a `ChatResult` (use `.content`), the
  LangChain path returns an `AIMessage` (use `.text`). Two stacks, two types.
- If the LangChain reply is the canned offline message instead of your script,
  you called `get_lc_model()` without passing `scripted_responses` through.
- `ChatMessage` validation error: `role` must be exactly `"system"`,
  `"user"`, or `"assistant"`.

### Stretch

Point both paths at a real provider (set `OPENAI_API_KEY` in `.env`) and ask
the same question. Compare the two error messages you get when you set a wrong
`OPENAI_BASE_URL` — which stack tells you more about what went wrong?

---

## Lab B — Prompt template

### Scenario

HR keeps asking the assistant for policy drafts — remote work today, expense
reporting tomorrow. Instead of a new hardcoded prompt per request, you build
one reusable template with the knobs HR actually turns.

### Objectives

- Build a `ChatPromptTemplate` with exactly five variables: `policy_type`,
  `audience`, `length`, `constraints`, `output_format`.
- See templates fail loudly when a variable is missing.

### Steps

1. Implement `build_policy_prompt()` using `ChatPromptTemplate.from_messages`:
   a `("system", ...)` message establishing TechCorp's policy writer role, and
   a `("user", ...)` message containing all five `{placeholders}`.
2. Run the starter file: `main_lab_b` renders the template with
   `SAMPLE_REQUEST` and prints the concrete messages.
3. Inspect `build_policy_prompt().input_variables` in the output of a quick
   `uv run python -c ...` — it should list exactly the five names.
4. Note what `main_lab_b` prints when it renders with only `policy_type`: the
   `KeyError` names the first missing variable. That error is a feature.

### Checkpoints

- [ ] `main_lab_b` prints a system + user message with all five values filled in.
- [ ] The missing-variable render prints a `KeyError`.
- [ ] Both `test_lab_b_*` tests pass.

### Debugging hints

- `input_variables` has extra entries? Any `{word}` in your text becomes a
  variable. Escape literal braces as `{{` and `}}`.
- `input_variables` missing one? Check spelling — `{ouput_format}` silently
  creates a *different* variable and the tests will catch it.
- Template renders but a value is missing from the output: you probably put a
  variable only in a message the test doesn't check — keep all five in the
  rendered content.

### Stretch

Add an optional sixth variable with a default using
`.partial(tone="neutral")` — confirm `input_variables` shrinks to five again
and the template still renders.

---

## Lab C — Structured output

### Scenario

The assistant's policy answers get displayed in TechCorp's intranet UI, which
needs fields — a title, a bullet list of rules — not a blob of prose. You make
the model return a validated `PolicySummary` object.

### Objectives

- Bind `PydanticOutputParser` to the provided `PolicySummary` model.
- Embed the parser's format instructions in a prompt.
- Run render → generate → validate as three explicit stages.

### Steps

1. Implement `build_summary_parser()`: return
   `PydanticOutputParser(pydantic_object=PolicySummary)`.
2. Print `parser.get_format_instructions()` once and read it — this is the
   text that tells the model what JSON to produce.
3. Implement `summarize_policy(policy_text, model)`:
   - build the parser;
   - build a `ChatPromptTemplate` whose system message includes
     `{format_instructions}` and whose user message carries `{policy_text}`;
   - pre-fill the instructions with
     `.partial(format_instructions=parser.get_format_instructions())`;
   - run the stages by hand: `prompt.invoke({...})` → `model.invoke(messages)`
     → `parser.parse(reply.text)`; return the result.
4. Run the starter file: `main_lab_c` drives your function with a scripted
   model that returns `SAMPLE_SUMMARY_JSON` and prints the typed fields.
5. Read the docstring note: on a live provider the same result comes from
   `model.with_structured_output(PolicySummary)` with no parser at all —
   that's the optional `-m live` test.

### Checkpoints

- [ ] `main_lab_c` prints `type : PolicySummary` and populated
      `key_rules` / `exceptions` lists.
- [ ] `test_lab_c_returns_a_populated_policy_summary_from_scripted_json` passes.

### Debugging hints

- `KeyError: 'format_instructions'` at invoke time: you declared the
  placeholder but never `.partial(...)`-ed it (or passed it in the input
  dict). One of the two must supply it.
- `OutputParserException`: the model's reply wasn't valid JSON for the schema.
  With the scripted model that means you parsed the wrong thing — make sure
  you feed `reply.text` (the message text), not the `AIMessage` object or the
  prompt.
- Format instructions contain literal `{` characters — that's why they must go
  in via `.partial`/input dict, **not** pasted directly into the template
  string (where braces would be parsed as variables).

### Stretch

Break the script on purpose: pass `scripted_responses=['{"title": "x"}']` and
watch the parser reject it. Which missing field does the validation error name
first?

---

## Lab D — Chain composition

### Scenario

Labs B and C gave you the parts; production wants one component. You compose
the policy-request prompt, a model, and the summary parser into a single
runnable: dict in, `PolicySummary` out.

### Objectives

- Compose `prompt | model | parser` with the pipe operator.
- Invoke the chain once and inspect the typed result.
- Understand that the composed chain is itself a Runnable.

### Steps

1. Implement `build_policy_chain(model)`:
   - build the parser (Lab C);
   - build a prompt that asks for a policy using **all five**
     `POLICY_VARIABLES` *and* embeds `{format_instructions}` in the system
     message (pre-filled via `.partial`, same trick as Lab C);
   - return `prompt | model | parser`.
2. Run the starter file: `main_lab_d` invokes your chain with
   `SAMPLE_REQUEST` and a scripted model, then accesses `result.key_rules[0]`
   — field access on a typed object, no JSON handling in sight.
3. Compare with Lab C: the three `invoke` calls you wrote by hand are now one.
   Same work, one seam.

### Checkpoints

- [ ] `main_lab_d` prints a `PolicySummary(...)` repr and the first rule.
- [ ] `test_lab_d_chain_invoke_returns_policy_summary_end_to_end` passes.
- [ ] Full module run is green: `uv run pytest course/03_langchain -q`.

### Debugging hints

- `TypeError` about `dict` and `|`: one of your three stages isn't a Runnable
  — a common slip is piping the `PolicySummary` class instead of the parser.
- `KeyError` on invoke: the chain's input dict must contain exactly the
  template's remaining variables — all five `POLICY_VARIABLES` (the
  format instructions were `.partial`-ed away).
- Chain returns an `AIMessage` instead of `PolicySummary`: you forgot the
  final `| parser` stage.

### Stretch

Call `chain.batch([SAMPLE_REQUEST, SAMPLE_REQUEST])` with a scripted model
holding two JSON replies — every Runnable gets `batch` (and `stream`, and
async variants) for free. That uniformity is the payoff of the Runnable
contract, and it's what Module 10's graphs plug into.
