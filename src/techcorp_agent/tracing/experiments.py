"""Experiments and regression comparison — "did this change help or hurt?".

An *experiment* runs a fixed set of evaluation examples through a *pipeline* and
records both a trace per example and the deterministic metrics from Module 09's
``evaluation`` package. Two experiments over the *same* examples can then be
diffed: :func:`compare_experiments` reports the per-metric delta and, crucially,
names the individual examples that got **worse** — the regression list.

This is the machinery behind the module's headline claim: you don't argue that a
prompt change is an improvement, you *measure* it, on the same dataset, and you
catch the regression before it ships. It reuses the deterministic metrics
verbatim (a judge may be layered on per example, but never replaces them).

The ``pipeline_fn`` contract is deliberately small so any pipeline fits it::

    pipeline_fn(example: dict) -> {
        "answer": str,
        "sources": list[str],
        "retrieved_doc_ids": list[str],   # rank order, for hit@k
        "abstained": bool,
    }

so the RAG pipeline, the whole capstone graph, or a hand-written stub all work.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from techcorp_agent.evaluation.metrics import (
    abstention_correct,
    fact_coverage,
    hit_rate_at_k,
    source_accuracy,
)
from techcorp_agent.tracing.tracer import LocalTracer

# The metrics we track per example and aggregate. Kept as a tuple so the report
# and the comparison iterate the same set of names.
METRIC_NAMES = ("hit_rate", "source_accuracy", "fact_coverage", "abstention_accuracy")

PipelineFn = Callable[[dict], dict]


class ExampleRow(BaseModel):
    """The scored outcome of one example within an experiment."""

    example_id: str
    category: str
    hit_rate: float
    source_accuracy: float
    fact_coverage: float
    abstention_accuracy: float
    answer: str
    latency_ms: float | None = None


@dataclass
class ExperimentResult:
    """The full outcome of one experiment: per-example rows plus aggregates."""

    name: str
    rows: list[ExampleRow]
    aggregates: dict[str, float]
    n: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def row_by_id(self) -> dict[str, ExampleRow]:
        return {row.example_id: row for row in self.rows}


def _aggregate(rows: list[ExampleRow]) -> dict[str, float]:
    """Mean of every tracked metric across ``rows`` (0.0 for each on empty input)."""
    n = len(rows)
    if n == 0:
        return {metric: 0.0 for metric in METRIC_NAMES}
    return {metric: sum(getattr(row, metric) for row in rows) / n for metric in METRIC_NAMES}


def run_experiment(
    name: str,
    pipeline_fn: PipelineFn,
    examples: list[dict],
    tracer: LocalTracer,
    k: int = 4,
) -> ExperimentResult:
    """Run ``examples`` through ``pipeline_fn``, tracing each and scoring with the
    deterministic ``evaluation`` metrics.

    Each example becomes one traced run named ``"<experiment> · <example id>"``
    with the pipeline output, sources, and per-metric scores logged as steps.
    ``tool_routing`` examples are skipped (they need the tool agent, not RAG —
    the same exclusion Module 09's runner makes), so an experiment scores exactly
    the retrieval-shaped examples.

    Returns an :class:`ExperimentResult` whose ``aggregates`` are the mean of each
    metric — matching what ``evaluation.summarize`` would compute on the same
    outcomes.
    """
    rows: list[ExampleRow] = []
    for example in examples:
        category = example.get("category", "uncategorized")
        if category == "tool_routing":
            continue

        with tracer.run(f"{name} · {example['id']}", {"question": example["question"]}) as run:
            output = pipeline_fn(example)
            answer = output.get("answer", "")
            sources = output.get("sources", [])
            retrieved = output.get("retrieved_doc_ids", [])
            abstained = bool(output.get("abstained", False))

            expected_sources = example.get("expected_sources", [])
            row = ExampleRow(
                example_id=example["id"],
                category=category,
                hit_rate=hit_rate_at_k(expected_sources, retrieved, k),
                source_accuracy=source_accuracy(expected_sources, sources),
                fact_coverage=fact_coverage(example.get("expected_facts", []), answer),
                abstention_accuracy=float(
                    abstention_correct(bool(example.get("should_abstain", False)), abstained)
                ),
                answer=answer,
                latency_ms=None,
            )
            run.log_step("pipeline", {"answer": answer, "sources": sources})
            run.log_step(
                "scores",
                {metric: getattr(row, metric) for metric in METRIC_NAMES},
            )
            run.set_output({"answer": answer, "sources": sources})
        # The tracer measured wall-clock latency for the run; carry it onto the row.
        row.latency_ms = run.latency_ms
        rows.append(row)

    return ExperimentResult(
        name=name,
        rows=rows,
        aggregates=_aggregate(rows),
        n=len(rows),
    )


def compare_experiments(
    baseline: ExperimentResult,
    candidate: ExperimentResult,
) -> dict[str, Any]:
    """Diff two experiments over the same examples into a regression report.

    Returns a dict with:

    - ``deltas``: per-metric ``candidate - baseline`` on the aggregates
      (negative = the candidate got worse on that metric);
    - ``regressions``: the list of examples whose **overall** per-example score
      dropped, each as ``{example_id, category, metric drops, baseline, candidate}``;
    - ``improvements``: symmetrically, the examples that improved;
    - ``regressed`` / ``improved``: booleans summarising the aggregate direction;
    - ``summary``: a one-line human verdict.

    "Overall per-example score" is the mean of the four metrics for that example,
    so a change that helps one metric but hurts another nets out honestly instead
    of hiding under a single headline number.
    """
    base_rows = baseline.row_by_id()
    cand_rows = candidate.row_by_id()
    shared_ids = [eid for eid in base_rows if eid in cand_rows]

    def mean_score(row: ExampleRow) -> float:
        return sum(getattr(row, metric) for metric in METRIC_NAMES) / len(METRIC_NAMES)

    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    for eid in shared_ids:
        base_row = base_rows[eid]
        cand_row = cand_rows[eid]
        base_score = mean_score(base_row)
        cand_score = mean_score(cand_row)
        if cand_score < base_score:
            regressions.append(_example_diff(eid, base_row, cand_row, base_score, cand_score))
        elif cand_score > base_score:
            improvements.append(_example_diff(eid, base_row, cand_row, base_score, cand_score))

    deltas = {
        metric: round(
            candidate.aggregates.get(metric, 0.0) - baseline.aggregates.get(metric, 0.0), 6
        )
        for metric in METRIC_NAMES
    }
    regressed = any(delta < 0 for delta in deltas.values()) or bool(regressions)
    improved = (
        all(delta >= 0 for delta in deltas.values()) and not regressions and bool(improvements)
    )

    return {
        "baseline": baseline.name,
        "candidate": candidate.name,
        "deltas": deltas,
        "regressions": regressions,
        "improvements": improvements,
        "regressed": regressed,
        "improved": improved,
        "summary": _verdict(baseline.name, candidate.name, deltas, regressions),
    }


def _example_diff(
    eid: str,
    base_row: ExampleRow,
    cand_row: ExampleRow,
    base_score: float,
    cand_score: float,
) -> dict[str, Any]:
    """Per-example diff record naming exactly which metrics moved and by how much."""
    metric_deltas = {
        metric: round(getattr(cand_row, metric) - getattr(base_row, metric), 6)
        for metric in METRIC_NAMES
        if getattr(cand_row, metric) != getattr(base_row, metric)
    }
    return {
        "example_id": eid,
        "category": base_row.category,
        "baseline_score": round(base_score, 4),
        "candidate_score": round(cand_score, 4),
        "delta": round(cand_score - base_score, 4),
        "metric_deltas": metric_deltas,
    }


def _verdict(
    baseline_name: str,
    candidate_name: str,
    deltas: dict[str, float],
    regressions: list[dict[str, Any]],
) -> str:
    """A one-line, human-readable verdict for the comparison."""
    if regressions:
        worst = ", ".join(r["example_id"] for r in regressions[:5])
        more = "" if len(regressions) <= 5 else f" (+{len(regressions) - 5} more)"
        return (
            f"REGRESSION: '{candidate_name}' is worse than '{baseline_name}' on "
            f"{len(regressions)} example(s): {worst}{more}."
        )
    if all(delta == 0 for delta in deltas.values()):
        return f"NO CHANGE: '{candidate_name}' matches '{baseline_name}' on every metric."
    return f"IMPROVED: '{candidate_name}' beats '{baseline_name}' with no per-example regressions."
