# Experiment Comparison Report

**Baseline:** `baseline`  
**Candidate:** `worsened-prompt`

## Verdict: REGRESSION DETECTED

The candidate regressed on: **fact_coverage, source_accuracy**. Do not ship this change until the drop is understood.

## Metrics

| metric | baseline | candidate | delta | status |
|---|---:|---:|---:|:--|
| abstention_accuracy | 100.00% | 100.00% | +0.00% | — flat |
| fact_coverage | 100.00% | 28.00% | -72.00% | 🔻 regression |
| hit_rate | 100.00% | 100.00% | +0.00% | — flat |
| llm_judge | 100.00% | 100.00% | +0.00% | — flat |
| source_accuracy | 100.00% | 28.00% | -72.00% | 🔻 regression |

## Reading this honestly

- **Deterministic first.** Every metric above except `llm_judge` is a
  repeatable string/set check. They are the evidence; the judge is a
  paraphrase-aware complement, never the sole signal.
- **A caught regression is the tool working**, not the agent failing —
  the point of Lab B is to deliberately break a prompt and confirm the
  drop is measured *before* a user sees it.
- **Flat is not the same as better.** A change that moves nothing on this
  dataset may still help (or hurt) on inputs the dataset does not cover.
