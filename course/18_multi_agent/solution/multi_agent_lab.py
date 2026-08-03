"""Module 18 solution — the TechCorp multi-agent supervisor, measured honestly.

Runs fully offline:

    TECHCORP_OFFLINE=true uv run python course/18_multi_agent/solution/multi_agent_lab.py

It builds the three specialists, wires the supervisor, then runs the REQUIRED
comparison against the Module 14 single-agent graph on a slice of the evaluation
dataset — printing a table of LLM calls, tokens, latency, and failures for both
systems. The point is not to "win"; it is to read the numbers and decide when
the single agent is the better ship.
"""

from __future__ import annotations

import json
from pathlib import Path

from techcorp_agent.agents import (
    RunOutcome,
    SupervisorAgent,
    run_comparison,
    single_agent_outcome,
    write_comparison_report,
)
from techcorp_agent.capstone import build_graph, build_offline_store
from techcorp_agent.config import get_settings
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatResult

REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_PATH = REPO_ROOT / "data" / "evaluation" / "eval_dataset.json"

# A representative slice that exercises all three specialists (policy, support,
# orders) so the comparison is meaningful rather than one-sided.
QUESTIONS = [
    "How many vacation days do TechCorp employees get each year?",
    "How long is customer account data kept after an account deletion request?",
    "Is there a restocking fee if I return an opened product?",
    "How long is the standard warranty and does it cover water damage?",
    "Where is my order TC-1234 right now?",
    "Order TC-2048 hasn't shown up yet. What's going on with it?",
]


class _CountingMockLLM:
    """A MockLLMClient wrapper that totals LLM calls and token usage.

    The single-agent graph discards each ``ChatResult``'s usage, so to compare
    fairly we wrap the mock and accumulate ``.calls`` and token usage as they
    happen. (The supervisor tracks its own usage internally; this is only for
    the single-agent side.)
    """

    def __init__(self, inner: MockLLMClient) -> None:
        self._inner = inner
        self.name = inner.name
        self.llm_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    @property
    def calls(self):  # noqa: D401 - passthrough for anything reading .calls
        return self._inner.calls

    def complete(self, messages, *, temperature=0.0, max_tokens=None) -> ChatResult:
        result = self._inner.complete(messages, temperature=temperature, max_tokens=max_tokens)
        self.llm_calls += 1
        if result.usage:
            self.input_tokens += result.usage.input_tokens
            self.output_tokens += result.usage.output_tokens
        return result


def _single_agent_fn(store) -> callable:
    """Return ``fn(question) -> RunOutcome`` for the Module 14 single agent.

    Each call uses a FRESH counting-wrapped mock so per-question usage is clean,
    then adapts the final graph state + measured usage into a ``RunOutcome``.
    """

    def fn(question: str) -> RunOutcome:
        llm = _CountingMockLLM(MockLLMClient())
        app = build_graph(llm, store, mcp_registry=None)
        state = app.invoke(
            {"conversation_id": "cmp", "question": question, "trace": [], "loop_count": 0}
        )
        enriched = dict(state)
        enriched["_llm_calls"] = llm.llm_calls
        enriched["_input_tokens"] = llm.input_tokens
        enriched["_output_tokens"] = llm.output_tokens
        return single_agent_outcome(enriched)

    return fn


def _fresh_supervisor(store) -> SupervisorAgent:
    """A supervisor with its own fresh mock.

    Synthesis is ON here so the comparison shows the FULL cost of a realistic
    multi-agent design: a routing call, the specialist's call, and a synthesis
    call that rewrites the answer into one voice. That synthesis call is the
    honest premium the supervisor pays over the single agent — turn it off
    (``synthesize_with_llm=False``) and the supervisor merely ties the single
    agent on calls while still paying the routing/latency overhead, which is its
    own lesson (see the report).
    """
    return SupervisorAgent(store, MockLLMClient(), synthesize_with_llm=True)


def _print_table(results: dict) -> None:
    single = results["single_agent"]
    multi = results["supervisor"]
    delta = results["delta"]
    print("\n=== Multi-Agent vs Single-Agent (offline, mock LLM) ===")
    print(f"{'metric':<16}{'single':>12}{'supervisor':>14}{'delta':>10}")
    print("-" * 52)
    print(
        f"{'LLM calls':<16}{single['llm_calls']:>12}{multi['llm_calls']:>14}"
        f"{'+' + str(delta['extra_llm_calls']):>10}"
    )
    print(
        f"{'total tokens':<16}{single['total_tokens']:>12}{multi['total_tokens']:>14}"
        f"{'+' + str(delta['extra_tokens']):>10}"
    )
    print(
        f"{'latency (s)':<16}{single['latency_s']:>12.4f}{multi['latency_s']:>14.4f}"
        f"{delta['extra_latency_s']:>+10.4f}"
    )
    print(
        f"{'failures':<16}{single['failures']:>12}{multi['failures']:>14}"
        f"{delta['extra_failures']:>+10d}"
    )


def main() -> int:
    settings = get_settings()
    if not settings.offline:
        print("Note: this lab is written for offline mode. Set TECHCORP_OFFLINE=true.")

    store = build_offline_store()

    # Sanity: the dataset the comparison questions are drawn from exists.
    assert EVAL_PATH.exists(), f"missing eval dataset at {EVAL_PATH}"
    json.loads(EVAL_PATH.read_text(encoding="utf-8"))  # validate it parses

    results = run_comparison(
        QUESTIONS,
        single_agent_fn=_single_agent_fn(store),
        supervisor=_fresh_supervisor(store),
    )
    _print_table(results)

    report_path = settings.artifacts_dir / "module18_comparison.md"
    write_comparison_report(results, report_path)
    print(f"\nWrote comparison report -> {report_path}")

    # The honest conclusion, computed from the numbers.
    delta = results["delta"]
    same_sources = results["single_agent"]["sources"] == results["supervisor"]["sources"]
    print("\n--- When would you ship the single agent instead? ---")
    if same_sources and delta["extra_failures"] <= 0:
        print(
            "On these questions the supervisor cited the same sources as the single\n"
            f"agent while spending +{delta['extra_llm_calls']} LLM calls and\n"
            f"+{delta['extra_tokens']} tokens. Same answers, higher cost -> ship the\n"
            "single agent. Reach for the supervisor only when a specialist measurably\n"
            "improves quality or the single prompt has grown too big to route reliably."
        )
    else:
        print(
            "The supervisor's sources/failures differ from the single agent's here,\n"
            "so the extra cost may be buying real quality. Inspect the report's\n"
            "per-question source columns before deciding."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
