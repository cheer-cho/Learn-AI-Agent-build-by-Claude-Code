"""Module 04 solution — a deterministic prompt-output rubric.

Every scorer here is plain code: same input, same score, no API calls and no
LLM judge. That keeps the rubric fast, free, and — most importantly —
explainable: when a score drops you can point at exactly which check failed.

The trade-off is that code can only measure *proxies* for quality:

- constraint following  -> score_word_limit
- structure             -> score_required_headings / score_sections_present
- unsupported claims    -> score_no_unsupported_claims (approximate — see its
                           docstring; it only checks numeric facts against the
                           provided context, nothing more)

Deeper qualities (is the policy actually *good*?) still need a human — or,
later in the course (Module 19), a carefully-evaluated LLM judge.
All scores are floats in [0.0, 1.0].
"""

import re


def score_word_limit(text: str, limit: int) -> float:
    """1.0 if the text is non-empty and within `limit` words, else 0.0."""
    words = text.split()
    if not words:
        return 0.0
    return 1.0 if len(words) <= limit else 0.0


def score_required_headings(text: str, headings: list[str]) -> float:
    """Fraction of required headings that appear in the text (case-insensitive)."""
    if not headings:
        return 1.0
    lowered = text.lower()
    found = sum(1 for h in headings if h.lower() in lowered)
    return found / len(headings)


def score_sections_present(text: str, labels: list[str]) -> float:
    """Fraction of required section labels present (case-insensitive).

    Same mechanic as score_required_headings, but named for its Lab D job:
    checking that a decomposed answer produced all five labeled sections.
    """
    return score_required_headings(text, labels)


def score_no_unsupported_claims(text: str, context: str) -> float:
    """APPROXIMATE check that the output invents no facts beyond the context.

    Honest limitation: code cannot verify arbitrary claims. What it *can* do,
    for a small controlled case, is check the easiest-to-fabricate fact type —
    numbers. Every number in the output (a retention period, a fee, a
    deadline) must literally appear in the provided context; a policy that
    says "90-day retention" when the context only ever said "30-day" is
    inventing facts.

    Returns the fraction of numeric claims that are supported (1.0 when the
    output contains no numbers at all). A 1.0 here does NOT prove the text is
    fully grounded — prose claims are not checked. Module 09 builds the real
    grounding evaluation.
    """
    claimed = re.findall(r"\d+(?:\.\d+)?", text)
    if not claimed:
        return 1.0
    allowed = set(re.findall(r"\d+(?:\.\d+)?", context))
    supported = sum(1 for number in claimed if number in allowed)
    return supported / len(claimed)


def score_output(
    text: str,
    *,
    word_limit: int | None = None,
    headings: list[str] | None = None,
    section_labels: list[str] | None = None,
    context: str | None = None,
) -> dict[str, float]:
    """Run every applicable scorer and return {criterion: score}.

    Pass only the criteria that apply to the lab; the rest are omitted from
    the result so a lab is never penalized for a check it never claimed to meet.
    """
    scores: dict[str, float] = {}
    if word_limit is not None:
        scores["word_limit"] = score_word_limit(text, word_limit)
    if headings is not None:
        scores["headings"] = score_required_headings(text, headings)
    if section_labels is not None:
        scores["sections"] = score_sections_present(text, section_labels)
    if context is not None:
        scores["supported_claims"] = score_no_unsupported_claims(text, context)
    return scores


def total_score(scores: dict[str, float]) -> float:
    """Average of the criteria that were scored (0.0 for an empty dict)."""
    if not scores:
        return 0.0
    return sum(scores.values()) / len(scores)
