"""Request-cost estimation from token usage.

Rates are configurable because every provider (and model) prices differently.
The point is the habit: always know roughly what a request costs.
"""

from techcorp_agent.schemas import TokenUsage


def estimate_cost_usd(
    usage: TokenUsage,
    input_per_mtok: float,
    output_per_mtok: float,
) -> float:
    """Estimated USD cost of one request given per-1M-token rates."""
    if input_per_mtok < 0 or output_per_mtok < 0:
        raise ValueError("Token rates must be non-negative")
    return (usage.input_tokens * input_per_mtok + usage.output_tokens * output_per_mtok) / 1_000_000
