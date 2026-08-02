"""Module 09 tests — reference solution. Always runs, fully offline.

Everything here uses hash embeddings, a temporary Chroma store, and a
scripted mock LLM — no API key, no network, no credits.
"""

from pathlib import Path

import pytest

from techcorp_agent.config import Settings
from techcorp_agent.course_utils import import_from_path
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT, RAGPipeline
from techcorp_agent.schemas import Chunk
from techcorp_agent.vectorstore.chroma_store import VectorStore

MODULE_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def solution():
    return import_from_path("m09_solution_eval_lab", MODULE_DIR / "solution" / "eval_lab.py")


# --- the four metrics, hand-crafted boundary cases ----------------------------


def test_hit_rate_at_k_hit_and_miss(solution):
    assert solution.hit_rate_at_k(["doc-a"], ["doc-b", "doc-a"], k=2) == 1.0
    assert solution.hit_rate_at_k(["doc-c"], ["doc-a", "doc-b", "doc-c"], k=2) == 0.0
    assert solution.hit_rate_at_k(["doc-x"], ["doc-a", "doc-b"], k=4) == 0.0
    assert solution.hit_rate_at_k(["doc-a"], [], k=4) == 0.0


def test_hit_rate_at_k_vacuous_when_no_sources_expected(solution):
    assert solution.hit_rate_at_k([], ["doc-a"], k=4) == 1.0
    assert solution.hit_rate_at_k([], [], k=4) == 1.0


def test_source_accuracy_boundaries(solution):
    assert solution.source_accuracy(["doc-a"], ["doc-a"]) == 1.0
    assert solution.source_accuracy(["doc-a"], ["doc-a", "doc-x"]) == 0.5
    assert solution.source_accuracy([], []) == 1.0  # correct abstention
    assert solution.source_accuracy(["doc-a"], []) == 0.0  # missing citation
    assert solution.source_accuracy([], ["doc-a"]) == 0.0  # invented citation


def test_fact_coverage_boundaries(solution):
    assert solution.fact_coverage(["25 vacation days"], "You get 25 VACATION DAYS.") == 1.0
    assert solution.fact_coverage(["$500 per year", "receipts"], "It is $500 per year.") == 0.5
    assert solution.fact_coverage(["14 days"], "Nothing relevant.") == 0.0
    assert solution.fact_coverage([], "any answer") == 1.0
    # Documented limitation: paraphrases score 0.
    assert solution.fact_coverage(["25 vacation days"], "twenty-five days off") == 0.0


@pytest.mark.parametrize(
    ("should", "did", "expected"),
    [(True, True, True), (False, False, True), (True, False, False), (False, True, False)],
)
def test_abstention_correct(solution, should, did, expected):
    assert solution.abstention_correct(should, did) is expected


# --- run_and_report end-to-end -------------------------------------------------

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
    f"{ABSTENTION_TEXT}\nSOURCES: none",
]


def _pipeline(tmp_path: Path) -> RAGPipeline:
    store = VectorStore(HashEmbeddingClient(dimension=128), persist_dir=tmp_path / "chroma")
    store.add_chunks(
        [
            Chunk(
                id="test-dress-code#0",
                doc_id="test-dress-code",
                doc_title="Dress Code",
                category="employee_handbook",
                index=0,
                text="Business casual is the default dress code. "
                "Jeans are allowed at headquarters.",
            ),
            Chunk(
                id="test-refunds#0",
                doc_id="test-refunds",
                doc_title="Refund Policy",
                category="product_support",
                index=0,
                text="Damaged products qualify for a full refund within thirty days.",
            ),
        ]
    )
    return RAGPipeline(store, MockLLMClient(responses=list(SCRIPTED_RESPONSES)))


def test_run_and_report_scores_and_writes_report(solution, tmp_path: Path):
    out_path = tmp_path / "evaluation_report.md"
    results, summary = solution.run_and_report(
        _pipeline(tmp_path),
        EXAMPLES,
        out_path,
        context={"embedding client": "hash-embedding-128d", "llm": "mock-offline (scripted)"},
    )

    # tool_routing skipped; the two RAG examples scored.
    assert [r.example_id for r in results] == ["t-jeans", "t-moon"]
    jeans, moon = results
    assert jeans.hit == 1.0
    assert jeans.source_acc == 1.0
    assert jeans.fact_cov == 1.0
    assert jeans.abstention_ok is True
    assert moon.abstention_ok is True

    assert summary["overall"]["n"] == 2
    assert summary["overall"]["hit_rate"] == 1.0

    text = out_path.read_text(encoding="utf-8")
    assert "# TechCorp RAG Evaluation Report" in text
    assert "### answerable" in text  # per-category sections
    assert "### unanswerable" in text
    assert "hash-embedding-128d" in text  # run context is recorded
    assert "tool_routing" in text  # the exclusion is stated, not silent


def test_run_eval_script_end_to_end_offline(tmp_path: Path):
    """The deliverable: run_eval over the real corpus, forced fully offline."""
    run_eval = import_from_path("m09_solution_run_eval", MODULE_DIR / "solution" / "run_eval.py")
    settings = Settings(
        _env_file=None,
        openai_api_key="",
        techcorp_offline=True,  # hash embeddings + mock LLM, no downloads
        artifacts_dir=tmp_path / "artifacts",
    )
    report_path = run_eval.run(settings)

    assert report_path == tmp_path / "artifacts" / "evaluation_report.md"
    text = report_path.read_text(encoding="utf-8")
    assert "hit rate@k" in text
    assert "### paraphrase" in text  # real dataset categories made it through
    assert "### unanswerable" in text
    assert "mock-offline" in text  # context names the LLM that produced this
