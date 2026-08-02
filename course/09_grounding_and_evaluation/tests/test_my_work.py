"""Module 09 tests — your starter implementation.

These auto-skip while starter/eval_lab.py still contains TODO markers.
Once you finish the lab, they run and become your completion gate:

    uv run pytest course/09_grounding_and_evaluation -q
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import ABSTENTION_TEXT, RAGPipeline
from techcorp_agent.schemas import Chunk
from techcorp_agent.vectorstore.chroma_store import VectorStore

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/eval_lab.py still contains TODO markers — finish the lab first",
)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m09_starter_eval_lab", STARTER_DIR / "eval_lab.py")


# --- the four metrics, hand-crafted boundary cases ----------------------------


def test_hit_rate_at_k_hit_and_miss(my_work):
    assert my_work.hit_rate_at_k(["doc-a"], ["doc-b", "doc-a"], k=2) == 1.0
    assert my_work.hit_rate_at_k(["doc-c"], ["doc-a", "doc-b", "doc-c"], k=2) == 0.0
    assert my_work.hit_rate_at_k(["doc-x"], ["doc-a", "doc-b"], k=4) == 0.0
    assert my_work.hit_rate_at_k(["doc-a"], [], k=4) == 0.0


def test_hit_rate_at_k_vacuous_when_no_sources_expected(my_work):
    assert my_work.hit_rate_at_k([], ["doc-a"], k=4) == 1.0
    assert my_work.hit_rate_at_k([], [], k=4) == 1.0


def test_source_accuracy_boundaries(my_work):
    assert my_work.source_accuracy(["doc-a"], ["doc-a"]) == 1.0
    assert my_work.source_accuracy(["doc-a"], ["doc-a", "doc-x"]) == 0.5
    assert my_work.source_accuracy([], []) == 1.0  # correct abstention
    assert my_work.source_accuracy(["doc-a"], []) == 0.0  # missing citation
    assert my_work.source_accuracy([], ["doc-a"]) == 0.0  # invented citation


def test_fact_coverage_boundaries(my_work):
    assert my_work.fact_coverage(["25 vacation days"], "You get 25 VACATION DAYS.") == 1.0
    assert my_work.fact_coverage(["$500 per year", "receipts"], "It is $500 per year.") == 0.5
    assert my_work.fact_coverage(["14 days"], "Nothing relevant.") == 0.0
    assert my_work.fact_coverage([], "any answer") == 1.0
    assert my_work.fact_coverage(["25 vacation days"], "twenty-five days off") == 0.0


@pytest.mark.parametrize(
    ("should", "did", "expected"),
    [(True, True, True), (False, False, True), (True, False, False), (False, True, False)],
)
def test_abstention_correct(my_work, should, did, expected):
    assert my_work.abstention_correct(should, did) is expected


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


def test_run_and_report_scores_and_writes_report(my_work, tmp_path: Path):
    out_path = tmp_path / "evaluation_report.md"
    results, summary = my_work.run_and_report(
        _pipeline(tmp_path),
        EXAMPLES,
        out_path,
        context={"embedding client": "hash-embedding-128d", "llm": "mock-offline (scripted)"},
    )

    assert [r.example_id for r in results] == ["t-jeans", "t-moon"]  # tool_routing skipped
    assert results[0].hit == 1.0
    assert results[0].source_acc == 1.0
    assert results[0].fact_cov == 1.0
    assert results[1].abstention_ok is True
    assert summary["overall"]["n"] == 2

    text = out_path.read_text(encoding="utf-8")
    assert "### answerable" in text
    assert "### unanswerable" in text
    assert "hash-embedding-128d" in text
