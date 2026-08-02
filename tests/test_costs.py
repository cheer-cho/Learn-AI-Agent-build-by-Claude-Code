import pytest

from techcorp_agent.costs import estimate_cost_usd
from techcorp_agent.schemas import TokenUsage


def test_cost_calculation():
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=500_000)
    cost = estimate_cost_usd(usage, input_per_mtok=1.0, output_per_mtok=4.0)
    assert cost == pytest.approx(1.0 + 2.0)


def test_zero_usage_costs_nothing():
    assert estimate_cost_usd(TokenUsage(), 1.0, 4.0) == 0.0


def test_negative_rates_rejected():
    with pytest.raises(ValueError):
        estimate_cost_usd(TokenUsage(input_tokens=10), -1.0, 4.0)


def test_total_tokens_property():
    usage = TokenUsage(input_tokens=120, output_tokens=30)
    assert usage.total_tokens == 150
