"""Tests for the shared evaluation package (techcorp_agent.evaluation).

Fully offline: hash embeddings, a temporary Chroma store, and a scripted
mock LLM. These metrics gate Modules 09, 17, and 19, so the boundary
behavior is pinned down here in hand-crafted cases.
"""

from pathlib import Path

import pytest

from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.evaluation import (
    EvalResult,
    abstention_correct,
    fact_coverage,
    hit_rate_at_k,
    run_evaluation,
    source_accuracy,
    summarize,
    write_report,
)
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT, RAGPipeline
from techcorp_agent.vectorstore.chroma_store import VectorStore

# --- hit_rate_at_k -----------------------------------------------------------


def test_hit_when_expected_doc_in_top_k():
    assert hit_rate_at_k(["doc-a"], ["doc-b", "doc-a", "doc-c"], k=3) == 1.0


def test_hit_counts_any_of_several_expected_docs():
    assert hit_rate_at_k(["doc-a", "doc-z"], ["doc-z", "doc-b"], k=2) == 1.0


def test_miss_when_expected_doc_below_rank_k():
    assert hit_rate_at_k(["doc-c"], ["doc-a", "doc-b", "doc-c"], k=2) == 0.0


def test_miss_when_expected_doc_never_retrieved():
    assert hit_rate_at_k(["doc-x"], ["doc-a", "doc-b"], k=4) == 0.0


def test_miss_when_nothing_retrieved():
    assert hit_rate_at_k(["doc-a"], [], k=4) == 0.0


def test_hit_is_vacuous_when_no_sources_expected():
    # Unanswerable/ambiguous examples require no evidence: retrieval cannot miss.
    assert hit_rate_at_k([], ["doc-a"], k=4) == 1.0
    assert hit_rate_at_k([], [], k=4) == 1.0


# --- source_accuracy ---------------------------------------------------------


def test_source_accuracy_all_citations_expected():
    assert source_accuracy(["doc-a", "doc-b"], ["doc-a", "doc-b"]) == 1.0


def test_source_accuracy_partial_citations():
    assert source_accuracy(["doc-a"], ["doc-a", "doc-x"]) == 0.5


def test_source_accuracy_both_empty_is_perfect():
    # A correct abstention cites nothing and needed nothing.
    assert source_accuracy([], []) == 1.0


def test_source_accuracy_no_citations_but_sources_expected_fails():
    assert source_accuracy(["doc-a"], []) == 0.0


def test_source_accuracy_citations_for_unanswerable_fails():
    assert source_accuracy([], ["doc-a"]) == 0.0


# --- fact_coverage -----------------------------------------------------------


def test_fact_coverage_full_and_case_insensitive():
    answer = "You get 25 VACATION DAYS PER YEAR at TechCorp."
    assert fact_coverage(["25 vacation days per year"], answer) == 1.0


def test_fact_coverage_partial():
    answer = "The stipend is $500 per year."
    assert fact_coverage(["$500 per year", "receipts required"], answer) == 0.5


def test_fact_coverage_zero_when_facts_absent():
    assert fact_coverage(["14 days"], "No relevant facts here.") == 0.0


def test_fact_coverage_vacuous_when_no_facts_expected():
    assert fact_coverage([], "any answer at all") == 1.0
    assert fact_coverage([], "") == 1.0


def test_fact_coverage_is_literal_substring_matching():
    # Documented limitation: a correct paraphrase does not count.
    assert fact_coverage(["25 vacation days"], "You get twenty-five days off.") == 0.0


# --- abstention_correct ------------------------------------------------------


@pytest.mark.parametrize(
    ("should", "did", "expected"),
    [
        (True, True, True),  # correctly abstained
        (False, False, True),  # correctly answered
        (True, False, False),  # answered an unanswerable question
        (False, True, False),  # abstained on an answerable question
    ],
)
def test_abstention_correct(should, did, expected):
    assert abstention_correct(should, did) is expected


# --- runner end-to-end -------------------------------------------------------

EXAMPLES = [
    {
        "id": "t-jeans",
        "question": "Can I wear jeans at the office dress code?",
        "category": "answerable",
        "expected_sources": ["test-dress-code"],
        "expected_facts": ["jeans are allowed"],
        "should_abstain": False,
    },
    {
        "id": "t-refund",
        "question": "Do damaged products qualify for a refund after delivery?",
        "category": "answerable",
        "expected_sources": ["test-refunds"],
        "expected_facts": ["full refund", "thirty days"],
        "should_abstain": False,
    },
    {
        "id": "t-moon",
        "question": "What is the dress code policy for the Moon office?",
        "category": "unanswerable",
        "expected_sources": [],
        "expected_facts": [],
        "should_abstain": True,
    },
    {
        "id": "t-tool",
        "question": "What is 15% of $342.50?",
        "category": "tool_routing",
        "expected_sources": [],
        "expected_facts": ["51.375"],
        "should_abstain": False,
        "expected_tool": "calculator",
    },
]

SCRIPTED_RESPONSES = [
    "Yes, jeans are allowed at headquarters.\nSOURCES: test-dress-code",
    "Damaged products qualify for a full refund within thirty days.\nSOURCES: test-refunds",
    f"{ABSTENTION_TEXT}\nSOURCES: none",
]


@pytest.fixture
def pipeline(sample_corpus: Path, tmp_path: Path, hash_embeddings) -> RAGPipeline:
    store = VectorStore(hash_embeddings, persist_dir=tmp_path / "chroma")
    for doc in load_documents(sample_corpus):
        store.add_chunks(chunk_document(doc))
    return RAGPipeline(store, MockLLMClient(responses=list(SCRIPTED_RESPONSES)))


def test_run_evaluation_scores_controlled_examples(pipeline: RAGPipeline):
    results = run_evaluation(pipeline, EXAMPLES, k=4)

    # tool_routing is filtered out — it needs the Level 3 agent, not RAG.
    assert [r.example_id for r in results] == ["t-jeans", "t-refund", "t-moon"]
    assert all(isinstance(r, EvalResult) for r in results)

    jeans, refund, moon = results
    assert jeans.hit == 1.0
    assert jeans.source_acc == 1.0
    assert jeans.fact_cov == 1.0
    assert jeans.abstention_ok is True
    assert "jeans" in jeans.answer.lower()

    assert refund.hit == 1.0
    assert refund.source_acc == 1.0
    assert refund.fact_cov == 1.0
    assert refund.abstention_ok is True

    assert moon.hit == 1.0  # vacuous: no evidence was required
    assert moon.source_acc == 1.0  # nothing cited, nothing expected
    assert moon.abstention_ok is True
    assert moon.answer == ABSTENTION_TEXT


def test_summarize_aggregates_overall_and_per_category(pipeline: RAGPipeline):
    results = run_evaluation(pipeline, EXAMPLES, k=4)
    summary = summarize(results)

    assert summary["overall"]["n"] == 3
    assert summary["overall"]["hit_rate"] == 1.0
    assert summary["overall"]["abstention_accuracy"] == 1.0
    assert set(summary["per_category"]) == {"answerable", "unanswerable"}
    assert summary["per_category"]["answerable"]["n"] == 2
    assert summary["per_category"]["unanswerable"]["abstention_accuracy"] == 1.0


def test_summarize_handles_empty_results():
    summary = summarize([])
    assert summary["overall"]["n"] == 0
    assert summary["per_category"] == {}


def test_write_report_produces_markdown(pipeline: RAGPipeline, tmp_path: Path):
    results = run_evaluation(pipeline, EXAMPLES, k=4)
    summary = summarize(results)
    report_path = tmp_path / "reports" / "evaluation_report.md"

    returned = write_report(
        results,
        summary,
        report_path,
        context={"embedding client": "hash-embedding-128d", "llm": "mock-offline (scripted)"},
    )

    assert returned == report_path
    text = report_path.read_text(encoding="utf-8")
    assert "# TechCorp RAG Evaluation Report" in text
    # Context: the numbers are meaningless without knowing what produced them.
    assert "hash-embedding-128d" in text
    assert "mock-offline (scripted)" in text
    # Per-category sections and the tool_routing exclusion notice.
    assert "### answerable" in text
    assert "### unanswerable" in text
    assert "tool_routing" in text
    # Honest caveats.
    assert "substring" in text.lower()
