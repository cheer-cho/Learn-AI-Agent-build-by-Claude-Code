"""Tests for YOUR work in starter/explorer.py.

These auto-skip while starter/explorer.py still contains TODO markers.
Once you remove the TODOs, they run — and passing them all means you have
completed Module 01. Run with:

    uv run pytest course/01_llm_fundamentals/tests/test_my_work.py -q
"""

from pathlib import Path

import pytest

from techcorp_agent.course_utils import import_from_path, starter_incomplete
from techcorp_agent.llm.mock_client import MockLLMClient

MODULE_DIR = Path(__file__).resolve().parents[1]
STARTER_DIR = MODULE_DIR / "starter"

pytestmark = pytest.mark.skipif(
    starter_incomplete(STARTER_DIR),
    reason="starter/explorer.py still contains TODO markers — finish the lab first",
)

explorer = import_from_path("m01_starter_explorer", STARTER_DIR / "explorer.py")


class TestCountTokens:
    def test_returns_positive_ints(self):
        for text in ["a", "hello", explorer.APPLE_QUESTION, " ".join(explorer.NOISE_SENTENCES)]:
            count = explorer.count_tokens(text)
            assert isinstance(count, int)
            assert count > 0

    def test_monotonic_ish_with_length(self):
        short = "Sally has 14 apples."
        longer = explorer.APPLE_QUESTION
        longest = explorer.APPLE_QUESTION + " " + " ".join(explorer.NOISE_SENTENCES)
        assert explorer.count_tokens(short) < explorer.count_tokens(longer)
        assert explorer.count_tokens(longer) < explorer.count_tokens(longest)

    def test_heuristic_fallback_when_tiktoken_unavailable(self, monkeypatch):
        def boom():
            raise RuntimeError("no tiktoken vocabulary available offline")

        monkeypatch.setattr(explorer, "_load_encoding", boom)
        assert explorer.count_tokens("a" * 40) == 10
        assert explorer.count_tokens("hi") == 1  # never below 1

    def test_heuristic_fallback_when_encoding_is_none(self, monkeypatch):
        monkeypatch.setattr(explorer, "_load_encoding", lambda: None)
        assert explorer.count_tokens("a" * 80) == 20


class TestAddNoise:
    def test_increases_token_count(self):
        question = explorer.APPLE_QUESTION
        noisy = explorer.add_noise(question, 5)
        assert explorer.count_tokens(noisy) > explorer.count_tokens(question)

    def test_keeps_original_prompt(self):
        noisy = explorer.add_noise(explorer.APPLE_QUESTION, 3)
        assert noisy.endswith(explorer.APPLE_QUESTION)

    def test_cycles_past_list_length(self):
        n = len(explorer.NOISE_SENTENCES) + 4
        noisy = explorer.add_noise("q?", n)
        assert noisy.count(explorer.NOISE_SENTENCES[0]) >= 2

    def test_zero_noise_returns_prompt_unchanged(self):
        assert explorer.add_noise("q?", 0) == "q?"


class TestCompare:
    def test_scripted_mock_records_two_calls(self):
        client = MockLLMClient(responses=["The total is 16.", "Distracted, but still 16."])
        clean, noisy = explorer.compare_with_and_without_noise(
            client, explorer.APPLE_QUESTION, n_noise=4
        )
        assert clean.content == "The total is 16."
        assert noisy.content == "Distracted, but still 16."
        assert len(client.calls) == 2
        clean_prompt = client.calls[0][-1].content
        noisy_prompt = client.calls[1][-1].content
        assert clean_prompt == explorer.APPLE_QUESTION
        assert noisy_prompt.endswith(explorer.APPLE_QUESTION)
        assert len(noisy_prompt) > len(clean_prompt)


class TestEnforceBudget:
    def test_within_budget_returned_unchanged(self):
        text = "short prompt"
        assert explorer.enforce_budget(text, 1000, mode="reject") == text
        assert explorer.enforce_budget(text, 1000, mode="truncate") == text

    def test_reject_raises_actionable_valueerror(self):
        long_text = explorer.add_noise(explorer.APPLE_QUESTION, 20)
        with pytest.raises(ValueError) as excinfo:
            explorer.enforce_budget(long_text, 10, mode="reject")
        message = str(excinfo.value)
        assert "budget" in message.lower(), "message should mention the budget"
        assert any(ch.isdigit() for ch in message), "message should state token numbers"

    def test_truncate_fits_budget(self):
        long_text = explorer.add_noise(explorer.APPLE_QUESTION, 20)
        budget = 25
        truncated = explorer.enforce_budget(long_text, budget, mode="truncate")
        assert explorer.count_tokens(truncated) <= budget
        assert len(truncated) < len(long_text)

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="mode"):
            explorer.enforce_budget("text", 10, mode="explode")
