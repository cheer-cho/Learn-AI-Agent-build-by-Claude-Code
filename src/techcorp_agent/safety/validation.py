"""Input and output validation — the guardrails around a RAG answer.

Two directions, both cheap and both worth doing on every request:

- **Input validation** (:func:`validate_question`): reject empty, over-long, or
  obviously-malformed questions *before* spending a model call, with an
  actionable message the caller can show the user. Cheap rejection beats an
  expensive garbage answer.

- **Output validation** (:func:`validate_answer`): inspect the generated answer
  *before* returning it. Three checks the TechCorp grounding contract demands:

    1. Citations present when the answer makes company-specific claims.
    2. No cited source outside the retrieved set (no invented citations).
    3. Abstention text used verbatim when the model abstains.

Output validation is the last net under the injection defenses: if a hijacked
model tried to smuggle out data or answered without grounding, the missing /
invalid citations trip here even when detection missed the payload upstream.

These heuristics are conservative and honest — they catch the common failure
shapes, not every possible one. ``validate_answer`` returns a *report* (pass +
reasons) rather than raising, so the caller decides whether to block, warn, or
re-ask.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from techcorp_agent.rag.pipeline import ABSTENTION_TEXT

# Reasonable bounds for a single support/policy question. Tunable; the point is
# that *some* bound exists so a pasted megabyte can't drive cost or latency.
MIN_QUESTION_CHARS = 3
MAX_QUESTION_CHARS = 2000


@dataclass(frozen=True)
class ValidationReport:
    """Outcome of a validation check.

    Attributes:
        ok: True when the input/answer passed every check.
        reasons: human-readable failure reasons (empty when ``ok``). Each is
            phrased so a caller can show or log it directly.
    """

    ok: bool
    reasons: list[str] = field(default_factory=list)


def validate_question(question: str) -> ValidationReport:
    """Validate a user question before it reaches retrieval or the model.

    Rejects (with an actionable reason) questions that are empty/whitespace,
    too short to be meaningful, or too long to be a genuine question (a common
    shape for a pasted injection payload or an accidental file dump).

    Args:
        question: the raw user input.

    Returns:
        A :class:`ValidationReport`; ``ok`` is False with reasons on rejection.
    """
    reasons: list[str] = []
    stripped = (question or "").strip()
    if not stripped:
        reasons.append(
            "The question is empty. Please type a question about a TechCorp policy or order."
        )
    elif len(stripped) < MIN_QUESTION_CHARS:
        reasons.append(
            f"The question is too short (min {MIN_QUESTION_CHARS} characters). "
            "Please ask a full question."
        )
    if len(question or "") > MAX_QUESTION_CHARS:
        reasons.append(
            f"The question is too long ({len(question)} characters; max {MAX_QUESTION_CHARS}). "
            "Please shorten it to a single, specific question — long pasted text is rejected."
        )
    return ValidationReport(ok=not reasons, reasons=reasons)


# Company-specific claims tend to carry concrete specifics: money, durations,
# counts, dates. When an answer states such specifics it MUST be grounded (cite
# a source). Generic conversational replies ("I can help with that") need not.
_SPECIFIC_CLAIM_RE = re.compile(
    r"""
    \$\s?\d                    # a dollar amount, e.g. $250
    | \d+\s?%                  # a percentage, e.g. 5%
    | \b\d+\s+(?:day|days|hour|hours|week|weeks|month|months|business\s+days?)\b
    | \b\d{2,}\b               # any multi-digit number (limits, counts, ids)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _makes_company_specific_claim(answer: str) -> bool:
    """Heuristic: does the answer assert a concrete company-specific fact?

    Numbers, money, durations, and percentages are the tells. Deliberately
    conservative — it can miss a purely prose claim — so it is paired with the
    invalid-citation check rather than trusted alone.
    """
    return bool(_SPECIFIC_CLAIM_RE.search(answer))


def validate_answer(
    answer: str,
    retrieved_sources: list[str],
    cited_sources: list[str] | None = None,
) -> ValidationReport:
    """Check a generated answer against the TechCorp grounding contract.

    Args:
        answer: the answer text (already split from the ``SOURCES:`` line by
            ``rag.pipeline.parse_answer`` — pass the text and the parsed sources
            separately).
        retrieved_sources: doc ids that were actually supplied as context. The
            legitimate citation set; anything outside it is invented.
        cited_sources: the doc ids the answer claims as sources. Defaults to
            ``[]`` (no citation line).

    Returns:
        A :class:`ValidationReport`. Checks, in order:

        1. **Abstention format** — if the answer abstains, it must use
           ``ABSTENTION_TEXT`` verbatim and cite nothing.
        2. **Invalid citations** — every cited id must be in
           ``retrieved_sources``.
        3. **Missing citations** — a company-specific claim (money, durations,
           counts, %) must carry at least one citation.
    """
    cited = cited_sources or []
    reasons: list[str] = []

    abstained = ABSTENTION_TEXT.lower() in answer.lower()
    if abstained:
        # An abstaining answer must be *exactly* the abstention text and cite
        # nothing — a partial abstention that still asserts facts is a smell.
        if answer.strip() != ABSTENTION_TEXT:
            reasons.append(
                "Answer abstains but does not use the exact abstention wording — "
                "an abstention must be the abstention text verbatim, with no extra claims."
            )
        if cited:
            reasons.append("Answer abstains but still cites sources — an abstention cites nothing.")
        return ValidationReport(ok=not reasons, reasons=reasons)

    invalid = [s for s in cited if s not in set(retrieved_sources)]
    if invalid:
        reasons.append(
            "Answer cites sources that were not retrieved: "
            f"{', '.join(sorted(invalid))}. Only supplied context may be cited "
            "(a common sign of a hallucinated or hijacked answer)."
        )

    if _makes_company_specific_claim(answer) and not cited:
        reasons.append(
            "Answer states company-specific details (numbers, amounts, or durations) "
            "but cites no source. Company-specific claims must be grounded in a "
            "retrieved document or the answer must abstain."
        )

    return ValidationReport(ok=not reasons, reasons=reasons)
