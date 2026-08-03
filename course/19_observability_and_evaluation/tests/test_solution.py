"""Module 19 tests — reference solution. Always runs, fully offline.

Proves the solution's three labs run end to end against the real corpus with hash
embeddings and the mock LLM: Lab A writes traces, Lab B/C run the baseline and the
sabotaged candidate, and the comparison catches the regression. The deep unit
tests for the tracing package live in the permanent suite at ``tests/test_tracing.py``.
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path

MODULE_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def solution():
    return import_from_path(
        "m19_solution_observability_lab", MODULE_DIR / "solution" / "observability_lab.py"
    )


@pytest.fixture(scope="module")
def tracer(solution, tmp_path_factory):
    from techcorp_agent.tracing import LocalTracer

    return LocalTracer(tmp_path_factory.mktemp("m19-sol") / "runs.jsonl")


def test_lab_a_traces_each_demo_question(solution, tmp_path_factory):
    from techcorp_agent.tracing import LocalTracer

    path = tmp_path_factory.mktemp("m19-laba") / "runs.jsonl"
    solution.lab_a_trace_agent(LocalTracer(path))
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    # One traced run per demo question, each recording the router node.
    assert len(lines) == len(solution.DEMO_QUESTIONS)
    assert all('"node": "router"' in line for line in lines)


def test_examples_load_from_module09_dataset(solution):
    examples = solution.load_examples()
    assert len(examples) == 33  # the full Module 09 dataset
    assert {"id", "question", "category"} <= set(examples[0])


def test_baseline_and_candidate_experiments_and_regression(solution, tracer):
    from techcorp_agent.capstone import build_offline_store
    from techcorp_agent.tracing import compare_experiments, run_experiment

    store = build_offline_store()
    examples = solution.load_examples()

    baseline_fn = solution.make_grounded_pipeline(store, drop_citation_rule=False)
    candidate_fn = solution.make_grounded_pipeline(store, drop_citation_rule=True)

    baseline = run_experiment("baseline", baseline_fn, examples, tracer)
    candidate = run_experiment("no-citation-rule", candidate_fn, examples, tracer)

    # tool_routing examples are excluded, leaving the retrieval-shaped ones.
    assert baseline.n == candidate.n
    assert baseline.n > 0

    report = compare_experiments(baseline, candidate)
    # Dropping the citation rule tanks source accuracy and is caught.
    assert report["regressed"] is True
    assert report["deltas"]["source_accuracy"] < 0
    assert len(report["regressions"]) > 0
    assert "REGRESSION" in report["summary"]


def test_main_runs_end_to_end_and_catches_regression(solution, monkeypatch, tmp_path):
    # Point the trace file at a temp path so we don't touch the repo artifacts.
    monkeypatch.setattr(solution, "TRACE_PATH", tmp_path / "runs.jsonl")
    assert solution.main() == 0
    assert (tmp_path / "runs.jsonl").exists()
