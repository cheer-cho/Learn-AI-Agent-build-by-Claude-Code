"""Run the evaluation dataset through a RAGPipeline and report the results.

The dataset schema is `data/evaluation/eval_dataset.json`: each example has a
question, the document ids that hold the evidence (`expected_sources`), the
fact strings a complete answer must contain (`expected_facts`), and whether
the system should abstain. Examples in the `tool_routing` category are
skipped here — they need the tool-using agent from Level 3 (Module 11), not
the RAG pipeline — and the written report says so.

Introduced in Module 09; Modules 17 and 19 rerun the same evaluation to prove
that retrieval upgrades and observability work actually moved these numbers.
"""

from pathlib import Path

from pydantic import BaseModel

from techcorp_agent.evaluation.metrics import (
    abstention_correct,
    fact_coverage,
    hit_rate_at_k,
    source_accuracy,
)
from techcorp_agent.rag.pipeline import RAGPipeline

SKIPPED_CATEGORY = "tool_routing"

_TABLE_HEADER = (
    "| examples | hit rate@k | source accuracy | fact coverage | abstention accuracy |\n"
    "|---:|---:|---:|---:|---:|"
)


class EvalResult(BaseModel):
    """All metric outcomes for one evaluation example."""

    example_id: str
    category: str
    hit: float
    source_acc: float
    fact_cov: float
    abstention_ok: bool
    answer: str


def run_evaluation(pipeline: RAGPipeline, examples: list[dict], k: int = 4) -> list[EvalResult]:
    """Score every non-tool_routing example against the pipeline.

    Per example: retrieve (hit rate@k is computed from the retrieved chunks'
    doc ids, in rank order), then answer, then score the generation metrics
    on the returned `RAGAnswer`. `pipeline.answer` re-runs retrieval
    internally; retrieval is deterministic, so both calls see the same chunks.
    """
    results: list[EvalResult] = []
    for example in examples:
        category = example.get("category", "uncategorized")
        if category == SKIPPED_CATEGORY:
            continue
        expected_sources = example.get("expected_sources", [])

        retrieved = pipeline.retrieve(example["question"])
        doc_ids = [item.chunk.doc_id for item in retrieved]

        answer = pipeline.answer(example["question"])
        results.append(
            EvalResult(
                example_id=example["id"],
                category=category,
                hit=hit_rate_at_k(expected_sources, doc_ids, k),
                source_acc=source_accuracy(expected_sources, answer.sources),
                fact_cov=fact_coverage(example.get("expected_facts", []), answer.answer),
                abstention_ok=abstention_correct(
                    bool(example.get("should_abstain", False)), answer.abstained
                ),
                answer=answer.answer,
            )
        )
    return results


def summarize(results: list[EvalResult]) -> dict:
    """Aggregate the per-example metrics into overall and per-category means.

    Returns ``{"overall": stats, "per_category": {category: stats}}`` where
    each stats dict has n, hit_rate, source_accuracy, fact_coverage, and
    abstention_accuracy. Empty input yields n=0 and no categories.
    """

    def aggregate(subset: list[EvalResult]) -> dict:
        n = len(subset)
        if n == 0:
            return {
                "n": 0,
                "hit_rate": 0.0,
                "source_accuracy": 0.0,
                "fact_coverage": 0.0,
                "abstention_accuracy": 0.0,
            }
        return {
            "n": n,
            "hit_rate": sum(r.hit for r in subset) / n,
            "source_accuracy": sum(r.source_acc for r in subset) / n,
            "fact_coverage": sum(r.fact_cov for r in subset) / n,
            "abstention_accuracy": sum(1 for r in subset if r.abstention_ok) / n,
        }

    categories = sorted({result.category for result in results})
    return {
        "overall": aggregate(results),
        "per_category": {
            category: aggregate([r for r in results if r.category == category])
            for category in categories
        },
    }


def _stats_row(stats: dict) -> str:
    return (
        f"| {stats['n']} | {stats['hit_rate']:.0%} | {stats['source_accuracy']:.0%} "
        f"| {stats['fact_coverage']:.0%} | {stats['abstention_accuracy']:.0%} |"
    )


def write_report(results: list[EvalResult], summary: dict, path: Path, context: dict) -> Path:
    """Write a Markdown evaluation report and return its path.

    `context` documents the run configuration — at minimum which embedding
    client and which LLM produced these numbers, since the numbers are
    meaningless without that. Every key/value pair is rendered as-is.
    """
    path = Path(path)
    lines: list[str] = [
        "# TechCorp RAG Evaluation Report",
        "",
        "Deterministic evaluation of the Module 08 RAG pipeline against",
        "`data/evaluation/eval_dataset.json`.",
        "",
        "## Run context",
        "",
    ]
    lines.extend(f"- **{key}**: {value}" for key, value in context.items())
    lines += [
        "",
        "`tool_routing` examples were excluded from this run: they require the",
        "tool-using agent built in Level 3 (Module 11), not the RAG pipeline.",
        "",
        "## Overall",
        "",
        _TABLE_HEADER,
        _stats_row(summary["overall"]),
        "",
        "## Results by category",
    ]
    for category, stats in summary["per_category"].items():
        lines += ["", f"### {category}", "", _TABLE_HEADER, _stats_row(stats)]
    lines += [
        "",
        "## Reading these numbers honestly",
        "",
        "- **Retrieval vs generation.** Hit rate@k judges only what the vector",
        "  store returned; the other three judge what the model did with it.",
        "  When the LLM in the run context is the offline mock, the",
        "  generation-side numbers are placeholders that describe the mock,",
        "  not any real model — only the retrieval numbers are meaningful.",
        "- **Hash embeddings**, if used, match on word overlap only, so",
        "  paraphrase questions fail retrieval by construction; real semantic",
        "  embeddings score higher on that category.",
        "- **Fact coverage is a substring check.** A correct paraphrase of an",
        "  expected fact scores 0. Treat it as a floor, not a ceiling.",
        "- **Hit rate is vacuously 1.0** for examples that expect no sources",
        "  (unanswerable/ambiguous); those categories are judged by abstention",
        "  accuracy instead.",
        "- **All checks here are deterministic.** A model-based evaluator can",
        "  be layered on top (Module 19), but never replaces these checks.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
