"""Module 09 starter — implement the four evaluation metrics and the runner.

Work through lab.md and replace each TODO. The permanent copies of these
metrics live in src/techcorp_agent/evaluation/ (later modules import them
from there); your versions here must behave identically — the tests check
the same boundary cases against both.

Check it:
    uv run pytest course/09_grounding_and_evaluation -q
"""

from pathlib import Path

# Pre-wired imports: the shared runner pieces run_and_report needs (Task 4),
# and the pipeline type you are evaluating.
from techcorp_agent.evaluation import EvalResult, run_evaluation, summarize, write_report
from techcorp_agent.rag.pipeline import RAGPipeline

# --- Task 2: the four metrics ------------------------------------------------


def hit_rate_at_k(expected_sources: list[str], retrieved_doc_ids: list[str], k: int) -> float:
    """RETRIEVAL metric: 1.0 if any expected doc id is in the top-k retrieved.

    Must return 1.0 when expected_sources is empty: unanswerable/ambiguous
    examples require no evidence, so retrieval cannot have missed any.
    """
    # TODO: If expected_sources is empty, return 1.0.
    # TODO: Otherwise return 1.0 if any expected id appears among the FIRST k
    #       entries of retrieved_doc_ids (they are in rank order), else 0.0.
    raise NotImplementedError("hit_rate_at_k — see lab.md Task 2")


def source_accuracy(expected_sources: list[str], cited_sources: list[str]) -> float:
    """GENERATION metric: fraction of cited sources that were expected."""
    # TODO: If nothing was cited: return 1.0 when expected_sources is also
    #       empty (a correct abstention cites nothing), else 0.0 (an answer
    #       that should cite evidence but doesn't is a failure).
    # TODO: Otherwise return (number of cited sources that are expected)
    #       divided by (number of cited sources).
    raise NotImplementedError("source_accuracy — see lab.md Task 2")


def fact_coverage(expected_facts: list[str], answer_text: str) -> float:
    """GENERATION metric: fraction of expected facts present in the answer.

    Case-insensitive substring match — a deterministic approximation: a
    correct paraphrase of a fact scores 0. Empty expected_facts → 1.0.
    """
    # TODO: If expected_facts is empty, return 1.0.
    # TODO: Otherwise count how many fact strings appear (case-insensitively)
    #       inside answer_text and divide by len(expected_facts).
    raise NotImplementedError("fact_coverage — see lab.md Task 2")


def abstention_correct(should_abstain: bool, abstained: bool) -> bool:
    """GENERATION metric: did the system abstain exactly when it should have?"""
    # TODO: Return True exactly when the two flags agree (both directions of
    #       disagreement are failures).
    raise NotImplementedError("abstention_correct — see lab.md Task 2")


# --- Task 4: run the evaluation and write the report --------------------------


def run_and_report(
    pipeline: RAGPipeline,
    examples: list[dict],
    out_path: Path,
    context: dict | None = None,
) -> tuple[list[EvalResult], dict]:
    """Evaluate every non-tool_routing example and write the Markdown report.

    Mirrors the shared runner. Must return (results, summary).
    """
    # TODO: Call run_evaluation(pipeline, examples, k=4) to get the results
    #       (it already skips tool_routing examples).
    # TODO: Aggregate them with summarize(results).
    # TODO: Write the report with write_report(results, summary, out_path,
    #       context or {}).
    # TODO: Return (results, summary).
    raise NotImplementedError("run_and_report — see lab.md Task 4")
