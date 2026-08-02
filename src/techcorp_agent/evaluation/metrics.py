"""Deterministic RAG evaluation metrics.

The four metrics split along the line Module 09 teaches:

- retrieval evaluation — did the system fetch the required evidence?
  (`hit_rate_at_k`)
- generation evaluation — did the answer use that evidence faithfully?
  (`source_accuracy`, `fact_coverage`, `abstention_correct`)

All of them are plain string/set checks: cheap, repeatable, and honest about
what they can and cannot see. They are the required baseline for every
evaluation in this course — a model-based evaluator (Module 19) may be layered
on top, but must never be the only validation method.
"""


def hit_rate_at_k(expected_sources: list[str], retrieved_doc_ids: list[str], k: int) -> float:
    """1.0 if any expected document id appears among the top-k retrieved ids.

    `retrieved_doc_ids` is the chunk-level doc-id list in rank order (best
    first); duplicates from multi-chunk documents are fine and count toward k.

    Empty `expected_sources` (unanswerable / ambiguous examples) returns 1.0:
    no evidence is required, so retrieval cannot have missed it. Those
    examples are judged by `abstention_correct` instead — read per-category
    hit rates with that in mind.
    """
    if not expected_sources:
        return 1.0
    top_k = set(retrieved_doc_ids[:k])
    return 1.0 if any(doc_id in top_k for doc_id in expected_sources) else 0.0


def source_accuracy(expected_sources: list[str], cited_sources: list[str]) -> float:
    """Fraction of cited sources that were expected (citation precision).

    Boundary cases:

    - both empty → 1.0 (a correct abstention cites nothing, and nothing
      needed citing);
    - nothing cited while sources were expected → 0.0 (a grounded answer must
      cite its evidence — a missing citation is a failure, not a free pass);
    - citations present but none expected → 0.0 (citing sources for an
      unanswerable question means the system pretended to have evidence).
    """
    if not cited_sources:
        return 1.0 if not expected_sources else 0.0
    expected = set(expected_sources)
    return sum(1 for source in cited_sources if source in expected) / len(cited_sources)


def fact_coverage(expected_facts: list[str], answer_text: str) -> float:
    """Fraction of expected fact strings present, case-insensitively, in the answer.

    This is a deterministic approximation of answer completeness: it only
    detects a fact when the answer contains the fact string verbatim (ignoring
    case). A correct paraphrase — "you get twenty-five days off" for
    "25 vacation days per year" — scores 0 for that fact. That blindness is
    the price of a check that is free, instant, and never lies about what it
    matched; Module 19 adds a model-based evaluator on top for paraphrases.

    Empty `expected_facts` → 1.0 (nothing was required).
    """
    if not expected_facts:
        return 1.0
    answer = answer_text.lower()
    return sum(1 for fact in expected_facts if fact.lower() in answer) / len(expected_facts)


def abstention_correct(should_abstain: bool, abstained: bool) -> bool:
    """True when the system abstained exactly when it should have.

    Both failure directions matter: answering an unanswerable question is a
    hallucination risk; abstaining on an answerable one makes the assistant
    useless. This metric scores them symmetrically.
    """
    return should_abstain == abstained
