"""Observability and evaluation-at-scale for the TechCorp agent (Module 19).

The public surface, all offline-first:

- :class:`LocalTracer` / :class:`Run` — write one JSON line per run to
  ``artifacts/traces/runs.jsonl``; :func:`trace_agent` captures a capstone-graph
  invocation automatically from its ``state["trace"]``.
- :func:`run_experiment` / :func:`compare_experiments` / :class:`ExperimentResult`
  — run eval examples through a pipeline, reuse the deterministic metrics, and
  diff two runs into a regression report.
- :func:`llm_judge` / :func:`combine_scores` — an LLM-as-judge that *refines* but
  never *replaces* the deterministic gate.
- :func:`langsmith_enabled` / :class:`LangSmithBridge` — an optional live mirror
  to LangSmith, a silent no-op with no API key.
"""

from techcorp_agent.tracing.experiments import (
    ExampleRow,
    ExperimentResult,
    compare_experiments,
    run_experiment,
)
from techcorp_agent.tracing.judge import (
    build_judge_messages,
    combine_scores,
    llm_judge,
)
from techcorp_agent.tracing.langsmith_bridge import LangSmithBridge
from techcorp_agent.tracing.langsmith_bridge import enabled as langsmith_enabled
from techcorp_agent.tracing.tracer import (
    DEFAULT_TRACE_PATH,
    LocalTracer,
    Run,
    trace_agent,
)

__all__ = [
    "DEFAULT_TRACE_PATH",
    "ExampleRow",
    "ExperimentResult",
    "LangSmithBridge",
    "LocalTracer",
    "Run",
    "build_judge_messages",
    "combine_scores",
    "compare_experiments",
    "langsmith_enabled",
    "llm_judge",
    "run_experiment",
    "trace_agent",
]
