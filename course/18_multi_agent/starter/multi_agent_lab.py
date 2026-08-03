"""Module 18 starter — build the multi-agent supervisor and compare it honestly.

Work through the TODOs, then run:

    TECHCORP_OFFLINE=true uv run python course/18_multi_agent/starter/multi_agent_lab.py

Your completion gate:

    uv run pytest course/18_multi_agent -q

The tests in ``tests/test_my_work.py`` auto-skip until every TODO below is gone.

You are COMPOSING already-built pieces:
- ``PolicySpecialist`` / ``SupportSpecialist`` / ``OrdersSpecialist`` and
  ``SupervisorAgent`` live in ``techcorp_agent.agents`` — read them, don't
  reimplement them.
- ``build_graph`` / ``build_offline_store`` are the Module 14 single agent.
- ``run_comparison`` / ``write_comparison_report`` do the measuring.

Your job is the WIRING and the CONCLUSION, not the plumbing.
"""

from __future__ import annotations

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

# A representative slice that exercises all three specialists (policy, support,
# orders). Keep at least one of each so the comparison is not one-sided.
QUESTIONS = [
    "How many vacation days do TechCorp employees get each year?",
    "How long is customer account data kept after an account deletion request?",
    "Is there a restocking fee if I return an opened product?",
    "How long is the standard warranty and does it cover water damage?",
    "Where is my order TC-1234 right now?",
    "Order TC-2048 hasn't shown up yet. What's going on with it?",
]


class _CountingMockLLM:
    """Wraps a MockLLMClient to total the single agent's LLM calls and tokens.

    The single-agent graph throws away each ``ChatResult``'s usage, so we
    accumulate it here to compare fairly against the supervisor (which tracks
    its own usage). This helper is complete — you do not need to change it.
    """

    def __init__(self, inner: MockLLMClient) -> None:
        self._inner = inner
        self.name = inner.name
        self.llm_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    @property
    def calls(self):
        return self._inner.calls

    def complete(self, messages, *, temperature=0.0, max_tokens=None) -> ChatResult:
        result = self._inner.complete(messages, temperature=temperature, max_tokens=max_tokens)
        self.llm_calls += 1
        if result.usage:
            self.input_tokens += result.usage.input_tokens
            self.output_tokens += result.usage.output_tokens
        return result


def single_agent_fn(store):
    """Return ``fn(question) -> RunOutcome`` for the Module 14 single agent."""

    def fn(question: str) -> RunOutcome:
        llm = _CountingMockLLM(MockLLMClient())
        # TODO 1: build the single-agent graph over `store` with no MCP registry
        #         (mcp_registry=None), invoke it on `question`, and capture the
        #         final state. Seed the state with conversation_id, question,
        #         an empty trace list, and loop_count=0 (see tests/test_capstone).
        app = ...  # noqa: F841 - build_graph(llm, store, mcp_registry=None)
        state = ...  # noqa: F841 - app.invoke({...})

        # Attach the measured usage so single_agent_outcome can read it.
        enriched = dict(state)
        enriched["_llm_calls"] = llm.llm_calls
        enriched["_input_tokens"] = llm.input_tokens
        enriched["_output_tokens"] = llm.output_tokens
        return single_agent_outcome(enriched)

    return fn


def build_supervisor(store) -> SupervisorAgent:
    """Return a SupervisorAgent over `store` with its own fresh mock LLM.

    Decide: synthesis ON or OFF? With synthesis ON the supervisor spends an
    extra LLM call per question to rewrite the answer into one voice — that is
    the honest premium. Turn it on so the comparison SHOWS the full cost, then
    read the report and judge whether that premium bought anything.
    """
    # TODO 2: construct and return a SupervisorAgent(store, MockLLMClient(),
    #         synthesize_with_llm=...). Pick a value and be ready to justify it.
    ...


def main() -> int:
    settings = get_settings()
    store = build_offline_store()

    # TODO 3: run the comparison. Call run_comparison(QUESTIONS, ...) with your
    #         single_agent_fn(store) and build_supervisor(store), and keep the
    #         returned dict.
    results = ...

    # TODO 4: write the markdown report to
    #         settings.artifacts_dir / "module18_comparison.md" with
    #         write_comparison_report, and print where it went.

    # TODO 5: read the numbers and answer IN WRITING (a print is fine):
    #         "When would you ship the single agent instead?" Base your answer
    #         on results["delta"] and whether the source columns match.
    print(results)  # replace with your table + written conclusion
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
