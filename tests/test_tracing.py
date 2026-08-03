"""Permanent tests for the Module 19 tracing/observability package.

Fully offline and deterministic: a temp JSONL path per test, a hash-embedding
store built from the real corpus, and scripted ``MockLLMClient`` replies. No key,
no network, and no LangSmith account — the bridge is never exercised here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techcorp_agent.capstone import build_graph
from techcorp_agent.documents.chunking import chunk_document
from techcorp_agent.documents.loader import load_documents
from techcorp_agent.embeddings.hash_client import HashEmbeddingClient
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.tracing import (
    LocalTracer,
    combine_scores,
    compare_experiments,
    llm_judge,
    run_experiment,
    trace_agent,
)
from techcorp_agent.vectorstore.chroma_store import VectorStore

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"


# -- fixtures ---------------------------------------------------------------


@pytest.fixture
def trace_path(tmp_path) -> Path:
    return tmp_path / "traces" / "runs.jsonl"


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> VectorStore:
    persist = tmp_path_factory.mktemp("m19_chroma")
    vs = VectorStore(
        HashEmbeddingClient(dimension=256),
        persist_dir=persist,
        collection_name="m19_test",
    )
    for doc in load_documents(DATA_DIR):
        vs.add_chunks(chunk_document(doc))
    return vs


def _read_lines(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


# -- tracer: valid JSONL with all fields ------------------------------------


def test_tracer_writes_valid_jsonl_with_all_fields(trace_path):
    tracer = LocalTracer(trace_path)
    with tracer.run("agent", {"question": "hi"}) as run:
        run.log_step("router", {"route": "general"})
        run.set_output({"answer": "hello"})
        run.set_metrics(tokens={"total_tokens": 42}, latency_ms=1.5)

    records = _read_lines(trace_path)
    assert len(records) == 1
    record = records[0]
    for field in (
        "run_id",
        "timestamp",
        "name",
        "inputs",
        "steps",
        "output",
        "token_usage",
        "latency_ms",
        "error",
    ):
        assert field in record
    assert record["name"] == "agent"
    assert record["inputs"] == {"question": "hi"}
    assert record["token_usage"] == {"total_tokens": 42}
    assert record["latency_ms"] == 1.5
    assert record["error"] is None


def test_tracer_records_steps_in_order(trace_path):
    tracer = LocalTracer(trace_path)
    with tracer.run("agent") as run:
        run.log_step("router")
        run.log_step("retrieval")
        run.log_step("formatter")

    record = _read_lines(trace_path)[0]
    assert [step["node"] for step in record["steps"]] == ["router", "retrieval", "formatter"]


def test_tracer_appends_multiple_runs(trace_path):
    tracer = LocalTracer(trace_path)
    for i in range(3):
        with tracer.run(f"run-{i}") as run:
            run.set_output(i)
    assert len(_read_lines(trace_path)) == 3


# -- tracer: error runs captured, line still written -------------------------


def test_tracer_captures_error_and_still_writes_line(trace_path):
    tracer = LocalTracer(trace_path)
    with pytest.raises(ValueError):
        with tracer.run("boom", {"x": 1}) as run:
            run.log_step("before")
            raise ValueError("kaboom")

    records = _read_lines(trace_path)
    assert len(records) == 1
    record = records[0]
    assert record["error"] is not None
    assert "kaboom" in record["error"]
    assert "ValueError" in record["error"]
    # The step logged before the raise is preserved.
    assert [step["node"] for step in record["steps"]] == ["before"]


# -- trace_agent on a real capstone graph -----------------------------------


def test_trace_agent_records_router_and_formatter_nodes(store, trace_path):
    llm = MockLLMClient(
        responses=[
            "document_search",
            "Employees may work remotely.\nSOURCES: hr-remote-work",
        ]
    )
    app = build_graph(llm, store)
    tracer = LocalTracer(trace_path)

    state = trace_agent(app, "What is the remote work policy?", tracer, llm=llm)

    assert state["route"] == "retrieval"
    record = _read_lines(trace_path)[0]
    nodes = [step["node"] for step in record["steps"]]
    assert "router" in nodes
    assert "formatter" in nodes
    # The output carries the route + answer + sources captured from state.
    assert record["output"]["route"] == "retrieval"
    assert record["output"]["sources"] == ["hr-remote-work"]
    # Token usage was approximated from the mock client's recorded calls.
    assert record["token_usage"]["total_tokens"] > 0


# -- run_experiment aggregates match evaluation.metrics ----------------------


def _handmade_examples() -> list[dict]:
    return [
        {
            "id": "ex-answerable",
            "question": "How many vacation days?",
            "category": "answerable",
            "expected_sources": ["hr-vacation"],
            "expected_facts": ["25 vacation days"],
            "should_abstain": False,
        },
        {
            "id": "ex-unanswerable",
            "question": "Moon policy?",
            "category": "unanswerable",
            "expected_sources": [],
            "expected_facts": [],
            "should_abstain": True,
        },
    ]


def _good_pipeline(example: dict) -> dict:
    """A pipeline that answers both hand-made examples correctly."""
    if example["id"] == "ex-answerable":
        return {
            "answer": "You get 25 vacation days per year.",
            "sources": ["hr-vacation"],
            "retrieved_doc_ids": ["hr-vacation"],
            "abstained": False,
        }
    return {
        "answer": "I do not have enough information.",
        "sources": [],
        "retrieved_doc_ids": [],
        "abstained": True,
    }


def test_run_experiment_aggregates_match_metrics(trace_path):
    tracer = LocalTracer(trace_path)
    examples = _handmade_examples()
    result = run_experiment("good", _good_pipeline, examples, tracer, k=4)

    assert result.n == 2
    # Both examples are perfect, so every aggregate is 1.0.
    for metric, value in result.aggregates.items():
        assert value == pytest.approx(1.0), metric
    # One traced run per scored example.
    assert len(_read_lines(trace_path)) == 2


def test_run_experiment_skips_tool_routing(trace_path):
    tracer = LocalTracer(trace_path)
    examples = _handmade_examples() + [
        {"id": "ex-tool", "question": "2+2?", "category": "tool_routing", "expected_facts": []}
    ]
    result = run_experiment("mixed", _good_pipeline, examples, tracer)
    assert result.n == 2
    assert all(row.example_id != "ex-tool" for row in result.rows)


# -- REGRESSION TEST: baseline good, candidate bad, flagged ------------------


def _bad_pipeline(example: dict) -> dict:
    """A deliberately broken pipeline: no citations, no abstention, wrong facts."""
    if example["id"] == "ex-answerable":
        return {
            "answer": "Some vague answer with no numbers.",
            "sources": [],  # dropped the citation -> source_accuracy 0
            "retrieved_doc_ids": ["unrelated-doc"],  # missed the source -> hit@k 0
            "abstained": False,
        }
    # Answers the unanswerable one instead of abstaining -> abstention 0.
    return {
        "answer": "Sure, here's a made-up moon policy.",
        "sources": ["hr-vacation"],
        "retrieved_doc_ids": [],
        "abstained": False,
    }


def test_compare_experiments_flags_regression(trace_path):
    tracer = LocalTracer(trace_path)
    examples = _handmade_examples()
    baseline = run_experiment("baseline", _good_pipeline, examples, tracer)
    candidate = run_experiment("candidate-bad", _bad_pipeline, examples, tracer)

    report = compare_experiments(baseline, candidate)

    assert report["regressed"] is True
    assert report["improved"] is False
    # Both hand-made examples got worse.
    regressed_ids = {r["example_id"] for r in report["regressions"]}
    assert regressed_ids == {"ex-answerable", "ex-unanswerable"}
    # At least one aggregate delta is negative.
    assert any(delta < 0 for delta in report["deltas"].values())
    assert "REGRESSION" in report["summary"]


def test_compare_experiments_no_change_when_identical(trace_path):
    tracer = LocalTracer(trace_path)
    examples = _handmade_examples()
    baseline = run_experiment("a", _good_pipeline, examples, tracer)
    candidate = run_experiment("b", _good_pipeline, examples, tracer)
    report = compare_experiments(baseline, candidate)
    assert report["regressed"] is False
    assert report["regressions"] == []
    assert "NO CHANGE" in report["summary"]


# -- judge: scripted score + combine_scores gating ---------------------------


def test_llm_judge_returns_scripted_score():
    llm = MockLLMClient(responses=["SCORE: 4\nREASONING: mostly complete and faithful."])
    result = llm_judge(llm, "Q?", "A.", evidence="hr-vacation: 25 days")
    assert result["raw_score"] == 4
    assert result["score"] == pytest.approx(4 / 5)
    assert "faithful" in result["reasoning"]


def test_llm_judge_handles_unparseable_reply():
    llm = MockLLMClient(responses=["I refuse to follow the format."])
    result = llm_judge(llm, "Q?", "A.", evidence="")
    assert result["score"] == 0.0


def test_combine_scores_gates_on_deterministic_failure():
    # Judge loved it, but the deterministic gate failed -> overall failure.
    judge = {"score": 1.0, "reasoning": "looks great"}
    combined = combine_scores({"passed": False, "score": 0.0}, judge)
    assert combined["passed"] is False
    assert combined["score"] == 0.0
    assert combined["gate"] == "deterministic-fail"


def test_combine_scores_judge_refines_when_gate_passes():
    judge = {"score": 0.8, "reasoning": "minor omission"}
    combined = combine_scores({"passed": True, "score": 1.0}, judge)
    assert combined["passed"] is True
    assert combined["score"] == pytest.approx(0.8)
    assert combined["gate"] == "deterministic-pass"


def test_combine_scores_deterministic_only_when_no_judge():
    combined = combine_scores({"passed": True, "score": 1.0}, None)
    assert combined["passed"] is True
    assert combined["score"] == 1.0
    assert combined["judge_score"] is None
