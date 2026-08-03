"""Module 19 tests — your starter implementation.

These auto-skip while starter/observability_lab.py still contains TODO markers.
Once you finish the lab, they run and become your completion gate:

    uv run pytest course/19_observability_and_evaluation -q
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/observability_lab.py still contains TODO markers — finish the lab first",
)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m19_starter_observability_lab", STARTER_DIR / "observability_lab.py")


@pytest.fixture(scope="module")
def store():
    from techcorp_agent.capstone import build_offline_store

    return build_offline_store()


def test_lab_a_writes_a_trace_per_question(my_work, tmp_path):
    from techcorp_agent.tracing import LocalTracer

    path = tmp_path / "runs.jsonl"
    my_work.lab_a_trace_agent(LocalTracer(path))
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == len(my_work.DEMO_QUESTIONS)


def test_baseline_pipeline_cites_sources(my_work, store):
    """The baseline (citation rule kept) must credit a retrieved source."""
    baseline_fn = my_work.make_grounded_pipeline(store, drop_citation_rule=False)
    example = {
        "id": "eval-001",
        "question": "How many vacation days do TechCorp employees get each year?",
        "category": "answerable",
        "expected_sources": ["hr-vacation"],
        "expected_facts": ["25 vacation days"],
        "should_abstain": False,
    }
    out = baseline_fn(example)
    assert out["sources"], "baseline should cite at least one retrieved source"


def test_sabotaged_pipeline_drops_citations(my_work, store):
    """The sabotage (citation rule dropped) must produce no citations."""
    candidate_fn = my_work.make_grounded_pipeline(store, drop_citation_rule=True)
    example = {
        "id": "eval-001",
        "question": "How many vacation days do TechCorp employees get each year?",
        "category": "answerable",
        "expected_sources": ["hr-vacation"],
        "expected_facts": ["25 vacation days"],
        "should_abstain": False,
    }
    out = candidate_fn(example)
    assert out["sources"] == []


def test_regression_is_caught(my_work, tmp_path):
    from techcorp_agent.tracing import LocalTracer

    report = my_work.lab_bc_experiment_and_regression(LocalTracer(tmp_path / "runs.jsonl"))
    assert report["regressed"] is True
    assert report["deltas"]["source_accuracy"] < 0
