"""Module 19 — Observability and Evaluation at Scale (your working file).

Fill in the TODOs, then run:

    TECHCORP_OFFLINE=true uv run python \
        course/19_observability_and_evaluation/starter/observability_lab.py

Your completion gate (auto-skips until the TODOs are gone):

    uv run pytest course/19_observability_and_evaluation -q

The heavy lifting lives in the shared ``techcorp_agent.tracing`` package (the
``LocalTracer``, ``run_experiment``, ``compare_experiments``). This lab is about
*wiring* them into the three labs — instrument, experiment, catch the regression
— not reimplementing them. Read ``concepts.md`` first, then work top to bottom.
"""

from __future__ import annotations

import json
from pathlib import Path

from techcorp_agent.capstone import build_graph, build_offline_store
from techcorp_agent.config import get_settings
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.rag.pipeline import RAGPipeline, parse_answer
from techcorp_agent.tracing import (
    LocalTracer,
    compare_experiments,
    langsmith_enabled,
    run_experiment,
    trace_agent,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
TRACE_PATH = REPO_ROOT / "artifacts" / "traces" / "runs.jsonl"
EVAL_DATASET = REPO_ROOT / "data" / "evaluation" / "eval_dataset.json"

DEMO_QUESTIONS = [
    "How many vacation days do TechCorp employees get each year?",
    "What is 17.5% of 8,400?",
    "Where is my order TC-1234 right now?",
    "Hi there, thanks for the help!",
]


# --------------------------------------------------------------------------
# Lab A — instrument the agent and capture traces
# --------------------------------------------------------------------------


def lab_a_trace_agent(tracer: LocalTracer) -> None:
    """Record a handful of real agent runs into the JSONL trace log."""
    print("\n=== Lab A — instrument the agent ===")
    store = build_offline_store()
    for question in DEMO_QUESTIONS:
        llm = MockLLMClient()
        # TODO: invoke the capstone graph under the tracer with trace_agent(...).
        #   - build the graph with build_graph(llm, store)
        #   - pass the tracer and llm=llm so token usage is captured
        #   - keep the returned state so you can print state["route"]
        state = ...  # TODO: replace with the trace_agent(...) call
        print(f"  traced: route={state['route']:<10} q={question!r}")
    print(f"  -> wrote traces to {tracer.path}")
    print("  view with: uv run python scripts/view_traces.py")


# --------------------------------------------------------------------------
# Lab B / C — dataset, baseline experiment, and the deliberate regression
# --------------------------------------------------------------------------


def load_examples() -> list[dict]:
    """Load the Module 09 evaluation dataset (Lab B, step 1)."""
    data = json.loads(EVAL_DATASET.read_text(encoding="utf-8"))
    return data["examples"]


def make_grounded_pipeline(store, *, drop_citation_rule: bool = False):
    """Return a ``pipeline_fn(example) -> output`` over the real RAG pipeline.

    ``drop_citation_rule=True`` is the Lab C sabotage: it simulates a prompt edit
    that removed the "end with SOURCES:" rule, so the answer carries no citation
    line. Crucially it does this by *composition* — it never edits shared code.
    """

    def pipeline_fn(example: dict) -> dict:
        question = example["question"]
        retriever = RAGPipeline(store, MockLLMClient())
        retrieved = retriever.retrieve(question)
        doc_ids = [item.chunk.doc_id for item in retrieved]

        should_abstain = bool(example.get("should_abstain", False))
        if should_abstain or not retrieved:
            return {
                "answer": "I do not have enough information in the provided TechCorp documents "
                "to answer that question.",
                "sources": [],
                "retrieved_doc_ids": doc_ids,
                "abstained": True,
            }

        top_source = doc_ids[0] if doc_ids else ""
        facts = " ".join(example.get("expected_facts", []))
        body = f"Per TechCorp policy: {facts}".strip()
        # TODO: build the model reply string `raw`.
        #   - baseline  (drop_citation_rule=False): append "\nSOURCES: <top_source>"
        #   - sabotaged (drop_citation_rule=True):  NO SOURCES line at all
        raw = ...  # TODO: replace with the branching described above

        answer_text, sources = parse_answer(raw)
        supplied = set(doc_ids)
        sources = [s for s in sources if s in supplied]
        return {
            "answer": answer_text,
            "sources": sources,
            "retrieved_doc_ids": doc_ids,
            "abstained": False,
        }

    return pipeline_fn


def lab_bc_experiment_and_regression(tracer: LocalTracer) -> dict:
    """Run the baseline (Lab B) and the sabotaged candidate (Lab C), then compare."""
    print("\n=== Lab B — baseline experiment ===")
    store = build_offline_store()
    examples = load_examples()

    baseline_fn = make_grounded_pipeline(store, drop_citation_rule=False)
    # TODO: run the baseline experiment with run_experiment("baseline", ...).
    baseline = ...  # TODO
    print(f"  scored {baseline.n} examples")
    _print_aggregates(baseline.aggregates)

    print("\n=== Lab C — deliberately worsen the prompt, then catch it ===")
    candidate_fn = make_grounded_pipeline(store, drop_citation_rule=True)
    # TODO: run the candidate experiment with run_experiment("no-citation-rule", ...).
    candidate = ...  # TODO
    _print_aggregates(candidate.aggregates)

    # TODO: compare the two experiments into a regression report.
    report = ...  # TODO: compare_experiments(baseline, candidate)
    print("\n--- Regression report ---")
    print(f"  {report['summary']}")
    print("  per-metric deltas (candidate - baseline):")
    for metric, delta in report["deltas"].items():
        flag = "  <-- worse" if delta < 0 else ""
        print(f"    {metric:<22} {delta:+.3f}{flag}")
    print(f"  regressed examples: {len(report['regressions'])}")
    for row in report["regressions"][:5]:
        print(f"    - {row['example_id']} ({row['category']}) delta={row['delta']:+.3f}")
    return report


def _print_aggregates(aggregates: dict) -> None:
    parts = "  ".join(f"{metric}={value:.2f}" for metric, value in aggregates.items())
    print(f"    {parts}")


def main() -> int:
    settings = get_settings()
    print("Module 19 — Observability and Evaluation at Scale")
    print(f"  offline mode: {settings.offline}")
    live = "ENABLED" if langsmith_enabled() else "disabled (local fallback)"
    print(f"  LangSmith live path: {live}")

    tracer = LocalTracer(TRACE_PATH)
    lab_a_trace_agent(tracer)
    report = lab_bc_experiment_and_regression(tracer)

    if not report["regressed"]:
        print("\nUNEXPECTED: the deliberate regression was NOT caught — check the pipeline.")
        return 1
    print("\nDone. The deliberate regression was caught by the comparison above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
