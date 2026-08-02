# Checklist — Module 03: LangChain Fundamentals

Work through this after finishing `lab.md`. Every box should be honestly
tickable before you move on.

## Acceptance criteria

- [ ] `uv run python course/03_langchain/starter/langchain_labs.py` runs all
      four labs with no `TODO` messages and no errors — fully offline.
- [ ] `uv run pytest course/03_langchain -q` is green, including all
      `test_my_work.py` tests (they no longer skip).
- [ ] Lab A prints `identical : True` — the same scripted content came back
      through both the raw adapter and LangChain.
- [ ] My Lab A comparison table is filled in with my own words for all five
      dimensions (lines of code, portability, provider-feature visibility,
      error handling, testability).
- [ ] My policy template requires exactly `policy_type`, `audience`, `length`,
      `constraints`, `output_format` — and I saw the `KeyError` when one was
      missing.
- [ ] Lab C returned a `PolicySummary` instance, and I can explain the three
      stages I ran by hand (render → generate → validate).
- [ ] Lab D's chain does the same in one `invoke`, and I accessed a typed
      field (`result.key_rules[0]`) on the output.

## Understanding (say each answer out loud, or write it down)

- [ ] I can explain **what LangChain saved me and what it hid** in this
      module, with one concrete example of each from my own Lab A code.
- [ ] I can state the course definitions of **LLM** and **agent**, and explain
      why the Lab D chain is *not* an agent.
- [ ] I can explain why `techcorp_agent.llm.LLMClient` and LangChain's
      `BaseChatModel` are the same pattern (an adapter) at different
      altitudes.
- [ ] I can explain why the parser's format instructions go into the prompt
      via `.partial(...)` instead of being pasted into the template string.
- [ ] I know the difference between `PydanticOutputParser` (prompt-based,
      works offline) and `.with_structured_output(...)` (provider-native,
      needs a real key) — and when I'd pick each.
- [ ] I know that `chain.invoke(...)` is still a paid network call on a real
      provider, no matter how clean the pipe syntax looks.

## Wrap up

- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 03.
