"""Module 07 tests — your starter implementation.

These auto-skip while starter/chunking_experiment.py still contains TODO
markers. Once you finish Lab A, they run and become your completion gate:

    uv run pytest course/07_vector_database -q

Fully offline: hash embeddings and temporary directories only.
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.schemas import Document

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/chunking_experiment.py still contains TODO markers — finish Lab A first",
)

METRIC_KEYS = {
    "name",
    "strategy",
    "chunk_size",
    "overlap",
    "chunk_count",
    "avg_chunk_chars",
    "hit_rate",
    "duplicate_rate",
    "failures",
    "question_count",
    "top_k",
    "embedding_model",
}

ZEBRA_BODY = (
    "Zebras graze on savanna grass throughout the dry season. "
    "Zebra herds migrate long distances between grazing areas every year. "
    "A zebra foal can stand and walk within twenty minutes of birth. "
    "Zebra stripes confuse predators during a chase across the savanna plains."
)
GLACIER_BODY = (
    "Glaciers advance slowly downhill under their own enormous weight. "
    "Glacier ice compresses from accumulated snowfall over many centuries. "
    "Meltwater from glacier termini feeds rivers during warm summer months. "
    "Crevasses open where glacier flow accelerates over steep bedrock."
)


def make_documents() -> list[Document]:
    return [
        Document(
            id="doc-zebra",
            title="Zebra Facts",
            category="employee_handbook",
            content=ZEBRA_BODY,
        ),
        Document(
            id="doc-glacier",
            title="Glacier Facts",
            category="product_support",
            content=GLACIER_BODY,
        ),
    ]


QUESTIONS = [
    {
        "id": "q-zebra",
        "question": "How quickly can a zebra foal stand and walk after birth?",
        "expected_sources": ["doc-zebra"],
    },
    {
        "id": "q-glacier",
        "question": "What feeds rivers with glacier meltwater in summer months?",
        "expected_sources": ["doc-glacier"],
    },
]


@pytest.fixture(scope="module")
def my_work():
    return import_from_path(
        "m07_starter_chunking_experiment", STARTER_DIR / "chunking_experiment.py"
    )


@pytest.fixture
def embeddings() -> HashEmbeddingClient:
    return HashEmbeddingClient(dimension=128)


def test_run_config_returns_all_metric_keys_with_sane_ranges(my_work, embeddings, tmp_path):
    result = my_work.run_config(
        "tiny-fixed",
        "fixed",
        120,
        20,
        QUESTIONS,
        documents=make_documents(),
        embeddings=embeddings,
        persist_dir=tmp_path / "chroma",
    )
    assert METRIC_KEYS <= set(result), f"missing keys: {METRIC_KEYS - set(result)}"
    assert result["chunk_count"] > 0
    assert result["avg_chunk_chars"] > 0
    assert 0.0 <= result["hit_rate"] <= 1.0
    assert 0.0 <= result["duplicate_rate"] <= 1.0
    assert result["question_count"] == len(QUESTIONS)
    assert isinstance(result["failures"], list)
    hits = round(result["hit_rate"] * result["question_count"])
    assert hits + len(result["failures"]) == result["question_count"]


def test_run_config_finds_the_expected_sources(my_work, embeddings, tmp_path):
    result = my_work.run_config(
        "tiny-paragraph",
        "paragraph",
        400,
        0,
        QUESTIONS,
        documents=make_documents(),
        embeddings=embeddings,
        persist_dir=tmp_path / "chroma",
    )
    assert result["hit_rate"] == 1.0, f"unexpected failures: {result['failures']}"
    assert result["failures"] == []


def test_run_config_records_failures_for_unfindable_question(my_work, embeddings, tmp_path):
    questions = [
        {
            "id": "q-missing",
            "question": "completely unrelated wording quantum flux capacitor telemetry",
            "expected_sources": ["doc-that-does-not-exist"],
        }
    ]
    result = my_work.run_config(
        "tiny-fixed",
        "fixed",
        120,
        20,
        questions,
        documents=make_documents(),
        embeddings=embeddings,
        persist_dir=tmp_path / "chroma",
    )
    assert result["hit_rate"] == 0.0
    assert len(result["failures"]) == 1
    assert result["failures"][0]["id"] == "q-missing"


def test_duplicate_rate_identical_chunks_is_high(my_work):
    text = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"
    assert my_work.duplicate_rate([text, text, text]) == pytest.approx(1.0)


def test_duplicate_rate_disjoint_chunks_is_zero(my_work):
    a = "one two three four five six seven eight nine ten"
    b = "red orange yellow green blue indigo violet magenta cyan teal"
    assert my_work.duplicate_rate([a, b]) == 0.0


def test_duplicate_rate_handles_empty_and_short_chunks(my_work):
    assert my_work.duplicate_rate([]) == 0.0
    assert my_work.duplicate_rate(["too few words here"]) == 0.0


def test_write_report_produces_markdown_with_all_config_names(my_work, tmp_path):
    def fake_result(name: str) -> dict:
        return {
            "name": name,
            "strategy": "fixed",
            "chunk_size": 300,
            "overlap": 30,
            "chunk_count": 42,
            "avg_chunk_chars": 280.5,
            "hit_rate": 0.8,
            "duplicate_rate": 0.05,
            "failures": [
                {
                    "id": "eval-999",
                    "question": "Where is the moon base cafeteria?",
                    "expected_sources": ["moon-base"],
                    "retrieved_doc_ids": ["doc-a", "doc-b"],
                }
            ],
            "question_count": 15,
            "top_k": 4,
            "embedding_model": "hash-embedding-128d",
        }

    results = [fake_result("small-fixed"), fake_result("medium-fixed"), fake_result("paragraph")]
    report_path = tmp_path / "artifacts" / "chunking_report.md"
    returned = my_work.write_report(results, report_path)
    assert Path(returned) == report_path
    content = report_path.read_text(encoding="utf-8")
    for name in ("small-fixed", "medium-fixed", "paragraph"):
        assert name in content
    assert "hash-embedding-128d" in content, "report must state which embedding client ran"
    assert "word overlap" in content.lower(), "report must carry the hash-embedding caveat"
