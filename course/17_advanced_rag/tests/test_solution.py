"""Module 17 tests — reference solution. Always runs, fully offline.

Proves the experiment harness in solution/ runs end-to-end against the real
corpus with hash embeddings, and that it produces the five configurations and
an honest report. The deeper unit tests for the retrieval primitives live in
the permanent suite at tests/test_advanced_rag.py.
"""

from pathlib import Path

import pytest

from techcorp_agent.config import Settings
from techcorp_agent.course_utils import import_from_path
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient

MODULE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_DIR.parents[1]


@pytest.fixture(scope="module")
def solution():
    return import_from_path(
        "m17_solution_advanced_rag_lab", MODULE_DIR / "solution" / "advanced_rag_lab.py"
    )


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings(_env_file=None, openai_api_key="", techcorp_offline=True)


@pytest.fixture(scope="module")
def experiment_results(solution, settings, tmp_path_factory):
    documents = load_documents(settings.data_dir)
    examples = solution.load_scored_examples(settings)
    tmp = tmp_path_factory.mktemp("m17-exp")
    return solution.run_experiment(
        documents, HashEmbeddingClient(), examples, persist_dir=tmp
    ), examples


def test_all_five_configs_are_evaluated(experiment_results):
    results, _ = experiment_results
    assert [r.name for r in results] == ["baseline", "+hybrid", "+rerank", "+rewrite", "all"]


def test_scored_examples_are_the_retrieval_categories(solution, settings):
    examples = solution.load_scored_examples(settings)
    categories = {ex["category"] for ex in examples}
    assert categories == set(solution.SCORED_CATEGORIES)
    assert "unanswerable" not in categories  # excluded: hit@k vacuous there


def test_hybrid_beats_baseline_offline(experiment_results):
    """The measured, load-bearing claim: on hash embeddings, hybrid lifts hit@4."""
    results, _ = experiment_results
    by_name = {r.name: r for r in results}
    assert by_name["+hybrid"].hit_rate > by_name["baseline"].hit_rate


def test_every_config_reports_latency_and_n(experiment_results):
    results, examples = experiment_results
    for r in results:
        assert r.n == len(examples)
        assert r.avg_latency_ms >= 0.0
        assert 0.0 <= r.hit_rate <= 1.0


def test_write_report_produces_honest_table(solution, experiment_results, tmp_path):
    results, _ = experiment_results
    path = solution.write_report(
        results, None, tmp_path / "report.md", context={"embeddings": "hash-embedding-384d"}
    )
    text = path.read_text(encoding="utf-8")
    assert "hit@4" in text
    assert "Honest findings" in text
    # The report must name whichever techniques helped/hurt, not just assert wins.
    assert "HELPED" in text or "HURT" in text or "NO CHANGE" in text
