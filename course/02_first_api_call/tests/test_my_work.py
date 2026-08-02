"""Module 02 tests — your starter implementation.

These auto-skip while starter/first_call.py still contains TODO markers.
Once you finish the lab, they run and become your completion gate:

    uv run pytest course/02_first_api_call -q
"""

from pathlib import Path

import pytest

from techcorp_agent.config import Settings
from techcorp_agent.costs import estimate_cost_usd
from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage, ChatResult, TokenUsage

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/first_call.py still contains TODO markers — finish the lab first",
)


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, openai_api_key="", **overrides)


@pytest.fixture(scope="module")
def my_work():
    return import_from_path("m02_starter_first_call", STARTER_DIR / "first_call.py")


def test_build_messages_valid_roles_system_first(my_work):
    messages = my_work.build_messages("What is the refund policy?")
    assert messages, "build_messages must return at least one message"
    assert all(isinstance(m, ChatMessage) for m in messages)
    assert messages[0].role == "system", "the system message must come first"
    assert {m.role for m in messages} <= {"system", "user", "assistant"}
    assert any(m.role == "user" and "refund" in m.content for m in messages)


def test_run_request_returns_mock_content(my_work):
    client = MockLLMClient(responses=["Escalate refund requests to the billing team."])
    messages = my_work.build_messages("How do I handle refunds?")
    result = my_work.run_request(client, messages)
    assert isinstance(result, ChatResult)
    assert result.content == "Escalate refund requests to the billing team."
    assert client.calls == [messages], "the exact messages built must be what was sent"


def test_summarize_usage_handles_absent_usage(my_work, capsys):
    result = ChatResult(content="hello", model="mock-offline", usage=None)
    cost = my_work.summarize_usage(result, _settings())
    assert cost is None, "no usage reported means the cost is unknown (None)"
    assert "usage" in capsys.readouterr().out.lower()


def test_summarize_usage_cost_matches_estimate(my_work):
    settings = _settings(cost_input_per_mtok=2.50, cost_output_per_mtok=10.00)
    usage = TokenUsage(input_tokens=1_200, output_tokens=340)
    result = ChatResult(content="hello", model="test-model", usage=usage)
    expected = estimate_cost_usd(usage, 2.50, 10.00)
    assert my_work.summarize_usage(result, settings) == pytest.approx(expected)
