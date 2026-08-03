"""Module 19 — Observability and Evaluation at Scale (reference solution).

Runs Labs A-C end to end, fully offline, and prints the regression being caught:

    TECHCORP_OFFLINE=true uv run python \
        course/19_observability_and_evaluation/solution/observability_lab.py

- **Lab A — Instrument the agent.** Build the capstone graph offline and record
  a handful of real questions through ``trace_agent`` into
  ``artifacts/traces/runs.jsonl``. Then point ``scripts/view_traces.py`` at that
  file to see nodes/route/tokens/latency.
- **Lab B — Dataset + baseline experiment.** Load the Module 09 evaluation
  dataset and run the (good) grounded pipeline through ``run_experiment``.
- **Lab C — Deliberate regression, caught.** Build a *worsened* pipeline that
  drops the citation rule — WITHOUT editing any shared code, by composing a thin
  wrapper — re-run it as a second experiment, and ``compare_experiments`` catches
  the regression.

Everything imports from the shared ``techcorp_agent.tracing`` package built for
this module; nothing here reimplements the tracer or the metrics.
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

# A few representative questions that exercise several routes, so the trace log
# shows more than one kind of run.
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
        # A fresh mock client per question keeps token accounting per-run honest;
        # offline the keyword router + local tools answer without scripted replies.
        llm = MockLLMClient()
        state = trace_agent(build_graph(llm, store), question, tracer, llm=llm)
        print(f"  traced: route={state['route']:<10} q={question!r}")
    print(f"  -> wrote traces to {_display_path(tracer.path)}")
    print("  view with: uv run python scripts/view_traces.py")


def _display_path(path: Path) -> Path | str:
    """Show a repo-relative path when possible, else the path as-is."""
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


# --------------------------------------------------------------------------
# Lab B / C — dataset, baseline experiment, and the deliberate regression
# --------------------------------------------------------------------------


def load_examples() -> list[dict]:
    """Load the Module 09 evaluation dataset (Lab B, step 1)."""
    data = json.loads(EVAL_DATASET.read_text(encoding="utf-8"))
    return data["examples"]


def make_grounded_pipeline(store, *, drop_citation_rule: bool = False):
    """Return a ``pipeline_fn(example) -> output`` over the real RAG pipeline.

    ``drop_citation_rule=False`` is the honest baseline: it uses the shared
    ``RAGPipeline`` retrieval unchanged (cite sources or abstain).

    ``drop_citation_rule=True`` is the Lab C sabotage. It does NOT edit any shared
    code — instead it composes a thin wrapper that, after the pipeline answers,
    *strips the citations off the answer* before scoring, simulating a prompt
    change that removed rule 5 ("end with SOURCES:"). That is exactly the kind of
    well-meaning "simplify the prompt" edit whose damage you want observability to
    catch. See ``course/19.../concepts.md`` for why we override rather than mutate.

    Because the offline mock LLM can't be steered by a prompt edit, we make the
    two configurations *deterministic and different* with a scripted reply keyed
    off the example: the baseline reply carries a ``SOURCES:`` line, the sabotaged
    reply carries none — the observable effect of dropping the citation rule.
    """

    def pipeline_fn(example: dict) -> dict:
        question = example["question"]
        # Retrieve with the real shared pipeline so hit@k is genuine.
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

        # A faithful answer that mentions the expected facts, so fact_coverage is
        # high for the baseline. The citation line is present or absent depending
        # on whether the (simulated) prompt still carries the SOURCES rule.
        top_source = doc_ids[0] if doc_ids else ""
        facts = " ".join(example.get("expected_facts", []))
        body = f"Per TechCorp policy: {facts}".strip()
        if drop_citation_rule:
            raw = body  # no SOURCES line -> the model "forgot" to cite
        else:
            raw = f"{body}\nSOURCES: {top_source}"

        answer_text, sources = parse_answer(raw)
        # Only credit sources actually retrieved (the shared contract).
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
    baseline = run_experiment("baseline", baseline_fn, examples, tracer)
    print(f"  scored {baseline.n} examples")
    _print_aggregates(baseline.aggregates)

    print("\n=== Lab C — deliberately worsen the prompt, then catch it ===")
    print("  candidate: dropped the citation rule (no SOURCES line) — no shared code edited")
    candidate_fn = make_grounded_pipeline(store, drop_citation_rule=True)
    candidate = run_experiment("no-citation-rule", candidate_fn, examples, tracer)
    _print_aggregates(candidate.aggregates)

    report = compare_experiments(baseline, candidate)
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


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main() -> int:
    settings = get_settings()
    print("Module 19 — Observability and Evaluation at Scale")
    print(f"  offline mode: {settings.offline}")
    live = "ENABLED" if langsmith_enabled() else "disabled (local fallback)"
    print(f"  LangSmith live path: {live}")

    tracer = LocalTracer(TRACE_PATH)
    lab_a_trace_agent(tracer)
    report = lab_bc_experiment_and_regression(tracer)

    # The lab's whole point: the regression was caught by measurement, not vibes.
    if not report["regressed"]:
        print("\nUNEXPECTED: the deliberate regression was NOT caught — check the pipeline.")
        return 1
    print("\nDone. The deliberate regression was caught by the comparison above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
