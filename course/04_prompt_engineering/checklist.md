# Module 04 Checklist — Prompt Engineering

Work through this after finishing lab.md. Every box should be checkable from
the repository root, offline, with no API key.

## Understanding

- [ ] I can name the five ingredients of a working prompt (specificity, role,
      context, constraints, output format) and say which failure each one
      prevents in Lab A.
- [ ] I can define a "shot" and explain when zero-shot, one-shot, and
      few-shot are each the right choice.
- [ ] I can explain the few-shot trade-off: what the three exemplars cost per
      request, and what consistency they buy.
- [ ] I can explain why we request a plan, intermediate outputs, checkable
      calculations, a structured rationale, and evidence — instead of asking
      the model to reveal private hidden reasoning.
- [ ] I can state what `score_no_unsupported_claims` actually checks, and why
      a 1.0 from it does not prove an output is grounded.

## Working code — acceptance criteria

- [ ] `starter/prompts.py` and `starter/rubric.py` contain no `TODO` markers.
- [ ] `build_vague_prompt()` returns exactly `Write a policy.` and
      `build_specific_prompt()` includes `200-word`, `GDPR`, `30-day`,
      `European customers`, and all four headings, built from the constraints
      dict rather than hard-coded.
- [ ] `FEW_SHOT_EXEMPLARS` holds three exemplars I wrote, each showing
      empathetic tone, the shared response format, and the $500 / Tier 2
      escalation rule.
- [ ] `build_decomposed_prompt()` names all five sections
      (Applicable Requirements, Current-Policy Observations, Gaps,
      Recommendations, Implementation Steps) and restricts evidence to the
      included policy text.
- [ ] `uv run python course/04_prompt_engineering/solution/run_comparison.py`
      prints four score tables, and in every lab the strong (engineered)
      prompt's TOTAL beats the weak one's.
- [ ] I can point to the rubric row that exposes the weak output in each lab.
- [ ] `uv run pytest course/04_prompt_engineering -q` passes with **no
      skips** — `test_my_work.py` is running against my starter code and is
      green.

## Wrap up

- [ ] (Optional stretch) I ran one comparison in live mode and/or built a
      1.0-scoring bad output to find the rubric's blind spot.
- [ ] Return to [ROADMAP.html](../../ROADMAP.html) and tick off Module 04.
