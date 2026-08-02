"""Module 04 starter — a deterministic prompt-output rubric.

Every scorer is plain code: same input, same score, no API calls and no LLM
judge. Complete each function marked with `# TODO:`. All scores are floats in
[0.0, 1.0].
"""

import re


def score_word_limit(text: str, limit: int) -> float:
    """Return 1.0 if `text` is non-empty and within `limit` words, else 0.0.

    Hint: str.split() with no arguments splits on any whitespace.
    """
    # TODO: Count words and compare against the limit.
    raise NotImplementedError


def score_required_headings(text: str, headings: list[str]) -> float:
    """Return the fraction of `headings` found in `text` (case-insensitive).

    An empty headings list scores 1.0 (nothing was required).
    """
    # TODO: Count how many required headings appear and return the fraction.
    raise NotImplementedError


def score_sections_present(text: str, labels: list[str]) -> float:
    """Return the fraction of section `labels` present (case-insensitive).

    Same mechanic as score_required_headings, but named for its Lab D job:
    checking that a decomposed answer produced all five labeled sections.
    """
    # TODO: Reuse your heading check (or reimplement it) for section labels.
    raise NotImplementedError


def score_no_unsupported_claims(text: str, context: str) -> float:
    """APPROXIMATE check that the output invents no facts beyond the context.

    Code cannot verify arbitrary claims — so this checks the easiest-to-fake
    fact type: numbers. Every number in `text` must literally appear in
    `context`; return the fraction of numbers that do (1.0 if `text` has no
    numbers at all). Be honest in how you present this score: 1.0 does NOT
    prove the text is grounded — prose claims are not checked.

    Hint: re.findall(r"\\d+(?:\\.\\d+)?", ...) extracts the numbers.
    """
    # TODO: Extract numbers from text and context, return the supported fraction.
    raise NotImplementedError


def score_output(
    text: str,
    *,
    word_limit: int | None = None,
    headings: list[str] | None = None,
    section_labels: list[str] | None = None,
    context: str | None = None,
) -> dict[str, float]:
    """Run every applicable scorer and return {criterion: score}.

    Only score the criteria whose argument is not None, using these keys:
    "word_limit", "headings", "sections", "supported_claims".
    """
    # TODO: Call the scorers above for each provided criterion.
    raise NotImplementedError


def total_score(scores: dict[str, float]) -> float:
    """Return the average of the scored criteria (0.0 for an empty dict)."""
    # TODO: Average the scores.
    raise NotImplementedError
