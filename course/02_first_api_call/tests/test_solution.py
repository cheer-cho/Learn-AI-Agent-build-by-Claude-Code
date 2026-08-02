"""Module 02 tests — reference solution. Always runs, fully offline by default.

The single @pytest.mark.live test at the bottom spends real credits and only
runs with `uv run pytest course/02_first_api_call -m live`.
"""

import re
from pathlib import Path

import pytest

from techcorp_agent.config import Settings
from techcorp_agent.costs import estimate_cost_usd
from techcorp_agent.course_utils import import_from_path
from techcorp_agent.llm.base import ProviderError
from techcorp_agent.llm.mock_client import MockLLMClient
from techcorp_agent.schemas import ChatMessage, ChatResult, TokenUsage

MODULE_DIR = Path(__file__).resolve().parents[1]

# An API-key-shaped string: "sk-" plus 10+ key characters (total length > 12).
HARDCODED_KEY = re.compile(r"sk-[A-Za-z0-9_-]{10,}")


def _settings(**overrides) -> Settings:
    """Settings isolated from .env and with no API key, unless overridden."""
    return Settings(_env_file=None, openai_api_key="", **overrides)


@pytest.fixture(scope="module")
def solution():
    return import_from_path("m02_solution_first_call", MODULE_DIR / "solution" / "first_call.py")


def test_no_hardcoded_api_key_anywhere_in_module():
    for path in sorted(MODULE_DIR.rglob("*.py")):
        match = HARDCODED_KEY.search(path.read_text(encoding="utf-8"))
        assert match is None, f"possible hard-coded API key {match and match.group()!r} in {path}"


def test_build_messages_valid_roles_system_first(solution):
    messages = solution.build_messages("What is the refund policy?")
    assert messages, "build_messages must return at least one message"
    assert all(isinstance(m, ChatMessage) for m in messages)
    assert messages[0].role == "system", "the system message must come first"
    assert {m.role for m in messages} <= {"system", "user", "assistant"}
    assert any(m.role == "user" and "refund" in m.content for m in messages)


def test_run_request_returns_mock_content(solution):
    client = MockLLMClient(responses=["Escalate refund requests to the billing team."])
    messages = solution.build_messages("How do I handle refunds?")
    result = solution.run_request(client, messages)
    assert isinstance(result, ChatResult)
    assert result.content == "Escalate refund requests to the billing team."
    assert client.calls == [messages], "the exact messages built must be what was sent"


def test_summarize_usage_handles_absent_usage(solution, capsys):
    result = ChatResult(content="hello", model="mock-offline", usage=None)
    cost = solution.summarize_usage(result, _settings())
    assert cost is None, "no usage reported means the cost is unknown (None)"
    assert "usage" in capsys.readouterr().out.lower()


def test_summarize_usage_cost_matches_estimate(solution, capsys):
    settings = _settings(cost_input_per_mtok=2.50, cost_output_per_mtok=10.00)
    usage = TokenUsage(input_tokens=1_200, output_tokens=340)
    result = ChatResult(content="hello", model="test-model", usage=usage)
    expected = estimate_cost_usd(usage, 2.50, 10.00)
    assert solution.summarize_usage(result, settings) == pytest.approx(expected)
    out = capsys.readouterr().out
    assert "1200" in out.replace(",", "").replace("_", "")
    assert "1540" in out.replace(",", "").replace("_", "")  # total = input + output


def test_missing_key_raises_actionable_provider_error():
    from techcorp_agent.llm.openai_client import OpenAIChatClient

    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        OpenAIChatClient(_settings())


@pytest.mark.live
def test_live_ten_token_call(solution):
    """One tiny real call (max_tokens=10) — only with `pytest -m live` and a key."""
    from techcorp_agent.llm.factory import get_llm_client

    settings = Settings()
    if settings.offline:
        pytest.skip("OPENAI_API_KEY not configured (offline mode)")

    client = get_llm_client(settings)
    result = client.complete(solution.build_messages("Say hello."), max_tokens=10)
    assert isinstance(result, ChatResult)
    assert isinstance(result.content, str)
    assert result.model
    if result.usage is not None:
        assert result.usage.output_tokens <= 10 + 2  # small tolerance for provider counting
