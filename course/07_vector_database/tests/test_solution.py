"""Module 07 tests — reference solution. Always runs, fully offline.

Everything uses the deterministic HashEmbeddingClient and temporary
directories: no model download, no writes to the repo's artifacts/ or
.chroma/ directories.
"""

from pathlib import Path

import pytest

from techcorp_agent.config import get_settings
from techcorp_agent.course_utils import import_from_path
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.schemas import Chunk, Document
from techcorp_agent.vectorstore.chroma_store import VectorStore

MODULE_DIR = Path(__file__).resolve().parents[1]

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

# Distinct vocabularies so hash (word-overlap) embeddings retrieve reliably.
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


def make_chunks() -> list[Chunk]:
    return [
        Chunk(
            id="doc-zebra#0",
            doc_id="doc-zebra",
            doc_title="Zebra Facts",
            category="employee_handbook",
            index=0,
            text=ZEBRA_BODY,
        ),
        Chunk(
            id="doc-glacier#0",
            doc_id="doc-glacier",
            doc_title="Glacier Facts",
            category="product_support",
            index=0,
            text=GLACIER_BODY,
        ),
    ]


@pytest.fixture(scope="module")
def solution():
    return import_from_path(
        "m07_solution_chunking_experiment",
        MODULE_DIR / "solution" / "chunking_experiment.py",
    )


@pytest.fixture
def embeddings() -> HashEmbeddingClient:
    return HashEmbeddingClient(dimension=128)


# --- load_eval_questions -----------------------------------------------------


def test_load_eval_questions_filters_to_retrievable_categories(solution):
    questions = solution.load_eval_questions()
    assert len(questions) >= 10, "expected the answerable + paraphrase questions"
    for question in questions:
        assert question["question"].strip()
        assert question["expected_sources"], "retrieval questions must name a source doc"


# --- run_config ---------------------------------------------------------------


def test_run_config_returns_all_metric_keys_with_sane_ranges(solution, embeddings, tmp_path):
    result = solution.run_config(
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
    assert result["name"] == "tiny-fixed"
    assert result["chunk_count"] > 0
    assert result["avg_chunk_chars"] > 0
    assert 0.0 <= result["hit_rate"] <= 1.0
    assert 0.0 <= result["duplicate_rate"] <= 1.0
    assert result["question_count"] == len(QUESTIONS)
    assert result["embedding_model"] == embeddings.model_name
    assert isinstance(result["failures"], list)
    # hits + failures must account for every question
    hits = round(result["hit_rate"] * result["question_count"])
    assert hits + len(result["failures"]) == result["question_count"]


def test_run_config_finds_the_expected_sources(solution, embeddings, tmp_path):
    """Questions reusing a document's distinctive words must hit with hash embeddings."""
    result = solution.run_config(
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


def test_run_config_records_failures_for_unfindable_question(solution, embeddings, tmp_path):
    questions = [
        {
            "id": "q-missing",
            "question": "completely unrelated wording quantum flux capacitor telemetry",
            "expected_sources": ["doc-that-does-not-exist"],
        }
    ]
    result = solution.run_config(
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
    failure = result["failures"][0]
    assert failure["id"] == "q-missing"
    assert failure["expected_sources"] == ["doc-that-does-not-exist"]
    assert "retrieved_doc_ids" in failure


# --- duplicate_rate -----------------------------------------------------------


def test_duplicate_rate_identical_chunks_is_high(solution):
    text = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"
    assert solution.duplicate_rate([text, text, text]) == pytest.approx(1.0)


def test_duplicate_rate_disjoint_chunks_is_zero(solution):
    a = "one two three four five six seven eight nine ten"
    b = "red orange yellow green blue indigo violet magenta cyan teal"
    assert solution.duplicate_rate([a, b]) == 0.0


def test_duplicate_rate_handles_empty_and_short_chunks(solution):
    assert solution.duplicate_rate([]) == 0.0
    assert solution.duplicate_rate(["too few words here"]) == 0.0


# --- write_report -------------------------------------------------------------


def fake_result(name: str, model: str = "hash-embedding-128d") -> dict:
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
        "embedding_model": model,
    }


def test_write_report_produces_markdown_with_all_config_names(solution, tmp_path):
    results = [fake_result("small-fixed"), fake_result("medium-fixed"), fake_result("paragraph")]
    report_path = tmp_path / "artifacts" / "chunking_report.md"
    returned = solution.write_report(results, report_path)
    assert Path(returned) == report_path
    content = report_path.read_text(encoding="utf-8")
    assert content.lstrip().startswith("#"), "report should be Markdown with a heading"
    for name in ("small-fixed", "medium-fixed", "paragraph"):
        assert name in content
    assert "hash-embedding-128d" in content, "report must state which embedding client ran"
    assert "word overlap" in content.lower(), "report must carry the hash-embedding caveat"
    assert "eval-999" in content, "failure cases must be listed"


# --- VectorStore behavior the module teaches ----------------------------------


def test_vectorstore_persists_across_reopen(embeddings, tmp_path):
    persist_dir = tmp_path / "chroma"
    store = VectorStore(embeddings, persist_dir=persist_dir, collection_name="m07_persist")
    assert store.add_chunks(make_chunks()) == 2
    del store  # "application restart"

    reopened = VectorStore(embeddings, persist_dir=persist_dir, collection_name="m07_persist")
    assert reopened.count() == 2
    results = reopened.query("zebra foal walk", top_k=1)
    assert results and results[0].chunk.doc_id == "doc-zebra"


def test_vectorstore_metadata_category_filter(embeddings, tmp_path):
    store = VectorStore(embeddings, persist_dir=tmp_path / "chroma", collection_name="m07_filter")
    store.add_chunks(make_chunks())
    results = store.query("facts", top_k=4, category="product_support")
    assert results, "filtered query should still return the matching-category chunk"
    assert all(r.chunk.category == "product_support" for r in results)


def test_vectorstore_reset_empties_collection(embeddings, tmp_path):
    store = VectorStore(embeddings, persist_dir=tmp_path / "chroma", collection_name="m07_reset")
    store.add_chunks(make_chunks())
    assert store.count() == 2
    store.reset()
    assert store.count() == 0
    assert store.query("zebra", top_k=2) == []


def test_vectorstore_rejects_mismatched_embedding_model(embeddings, tmp_path):
    persist_dir = tmp_path / "chroma"
    VectorStore(embeddings, persist_dir=persist_dir, collection_name="m07_guard")
    other_model = HashEmbeddingClient(dimension=64)  # model_name: hash-embedding-64d
    with pytest.raises(ValueError, match="indexed with"):
        VectorStore(other_model, persist_dir=persist_dir, collection_name="m07_guard")


# --- end-to-end: run_experiment.py --------------------------------------------


def test_run_experiment_writes_report_offline(monkeypatch, tmp_path, capsys):
    """The main entry must run offline and write the artifact (into tmp here)."""
    monkeypatch.setenv("TECHCORP_OFFLINE", "true")
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    get_settings.cache_clear()
    try:
        runner = import_from_path(
            "m07_solution_run_experiment", MODULE_DIR / "solution" / "run_experiment.py"
        )
        assert runner.main() == 0
    finally:
        get_settings.cache_clear()

    report = tmp_path / "artifacts" / "chunking_report.md"
    assert report.exists(), "run_experiment.py must write artifacts/chunking_report.md"
    content = report.read_text(encoding="utf-8")
    assert "hash-embedding" in content, "offline run must state the hash client was used"
    assert "word overlap" in content.lower()
    out = capsys.readouterr().out
    assert "NOTICE" in out, "the offline fallback must announce itself"
