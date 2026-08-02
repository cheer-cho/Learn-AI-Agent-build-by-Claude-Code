"""Module 09 solution — the four evaluation metrics and the report runner.

The metric functions below are the reference for what you write in
starter/eval_lab.py. The permanent copies live in
src/techcorp_agent/evaluation/metrics.py (later modules import them from
there); your versions must behave identically — the tests check the same
boundary cases against both.

Run the full evaluation over the real corpus:
    uv run python course/09_grounding_and_evaluation/solution/run_eval.py
"""

from pathlib import Path

# run_and_report delegates to the shared runner so Modules 17 and 19 rerun
# the exact same evaluation; the metrics are reimplemented here so you can
# diff them against your own.
from techcorp_agent.evaluation import EvalResult, run_evaluation, summarize, write_report
from techcorp_agent.rag.pipeline import RAGPipeline

# --- Task 2: the four metrics ------------------------------------------------


def hit_rate_at_k(expected_sources: list[str], retrieved_doc_ids: list[str], k: int) -> float:
    """RETRIEVAL metric: 1.0 if any expected doc id is in the top-k retrieved.

    Empty expected_sources → 1.0 (no evidence required, nothing to miss);
    those examples are judged by abstention_correct instead.
    """
    if not expected_sources:
        return 1.0
    top_k = set(retrieved_doc_ids[:k])
    return 1.0 if any(doc_id in top_k for doc_id in expected_sources) else 0.0


def source_accuracy(expected_sources: list[str], cited_sources: list[str]) -> float:
    """GENERATION metric: fraction of cited sources that were expected.

    Both empty → 1.0 (a correct abstention cites nothing). Nothing cited
    while sources were expected → 0.0 (missing citations are a failure).
    """
    if not cited_sources:
        return 1.0 if not expected_sources else 0.0
    expected = set(expected_sources)
    return sum(1 for source in cited_sources if source in expected) / len(cited_sources)


def fact_coverage(expected_facts: list[str], answer_text: str) -> float:
    """GENERATION metric: fraction of expected facts present in the answer.

    Case-insensitive substring match — a deterministic approximation. A
    correct paraphrase scores 0; treat the number as a floor, not a ceiling.
    Empty expected_facts → 1.0.
    """
    if not expected_facts:
        return 1.0
    answer = answer_text.lower()
    return sum(1 for fact in expected_facts if fact.lower() in answer) / len(expected_facts)


def abstention_correct(should_abstain: bool, abstained: bool) -> bool:
    """GENERATION metric: did the system abstain exactly when it should have?"""
    return should_abstain == abstained


# --- Task 4: run the evaluation and write the report --------------------------


def run_and_report(
    pipeline: RAGPipeline,
    examples: list[dict],
    out_path: Path,
    context: dict | None = None,
) -> tuple[list[EvalResult], dict]:
    """Evaluate every non-tool_routing example and write the Markdown report.

    Mirrors the shared runner exactly (in fact, calls it): score each example,
    aggregate overall and per category, write the report to `out_path`.
    Returns (results, summary) so callers can print or assert on the numbers.
    """
    results = run_evaluation(pipeline, examples, k=4)
    summary = summarize(results)
    write_report(results, summary, out_path, context or {})
    return results, summary
