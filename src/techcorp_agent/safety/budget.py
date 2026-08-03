"""Per-session cost control: a running budget plus a guarded model call.

Two responsibilities:

- :class:`SessionBudget` — accumulates tokens and estimated USD cost across
  every call in a session, warns at a *soft* limit, and refuses further model
  calls at a *hard* limit by raising :class:`BudgetExceeded` with a clear,
  user-facing message. It reuses ``costs.estimate_cost_usd`` so the pricing
  logic lives in exactly one place.

- :func:`guarded_complete` — the wrapper every guarded call should go through.
  It enforces, in order: a hard-limit check *before* spending (fail closed), a
  ``max_tokens`` cap so output cost is bounded, a wall-clock *timeout* so a hung
  provider can't stall the session, and finally records the spend on the
  budget (emitting the soft-limit warning when crossed).

Why a budget at all? A single runaway loop, a retry storm, or an adversarial
"write me a 10,000-word essay" prompt can quietly ring up real money. A budget
turns "we noticed on the invoice" into "the session refused the call and told
the user why".
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field

from techcorp_agent.costs import estimate_cost_usd
from techcorp_agent.llm.base import LLMClient
from techcorp_agent.schemas import ChatMessage, ChatResult, TokenUsage


def _usd(amount: float) -> str:
    """Format a USD amount with enough precision to stay readable sub-cent.

    ``$0.50`` and ``$1.00`` read naturally at 2 dp, but a $0.003 budget would
    round to ``$0.00`` and confuse the reader — so amounts below a cent get 4 dp.
    """
    return f"${amount:.2f}" if amount >= 0.01 else f"${amount:.4f}"


class BudgetExceeded(RuntimeError):
    """Raised when a call is refused because the session hard limit is reached.

    The message is user-facing: it states the limit and what to do next.
    """


class ModelCallTimeout(RuntimeError):
    """Raised when a guarded model call exceeds its wall-clock timeout."""


@dataclass
class BudgetStatus:
    """A snapshot of a session's cumulative spend."""

    input_tokens: int
    output_tokens: int
    cost_usd: float
    soft_limit_usd: float
    hard_limit_usd: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def over_soft_limit(self) -> bool:
        return self.cost_usd >= self.soft_limit_usd

    @property
    def over_hard_limit(self) -> bool:
        return self.cost_usd >= self.hard_limit_usd


@dataclass
class SessionBudget:
    """Track cumulative token/cost spend for one session and enforce limits.

    Args:
        soft_limit_usd: at/above this cost, :meth:`record` returns a warning
            string (the session keeps working). A gentle "you're spending".
        hard_limit_usd: at/above this cost, further calls must be refused;
            :meth:`check_before_call` raises :class:`BudgetExceeded`.
        input_per_mtok / output_per_mtok: pricing, passed straight to
            ``estimate_cost_usd`` (USD per 1M tokens). Defaults match the
            course's ``config`` defaults.
    """

    soft_limit_usd: float = 0.50
    hard_limit_usd: float = 1.00
    input_per_mtok: float = 1.00
    output_per_mtok: float = 4.00

    input_tokens: int = field(default=0, init=False)
    output_tokens: int = field(default=0, init=False)
    cost_usd: float = field(default=0.0, init=False)
    _soft_warned: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.soft_limit_usd > self.hard_limit_usd:
            raise ValueError("soft_limit_usd must be <= hard_limit_usd")

    def status(self) -> BudgetStatus:
        """Return a snapshot of current spend against the limits."""
        return BudgetStatus(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost_usd=self.cost_usd,
            soft_limit_usd=self.soft_limit_usd,
            hard_limit_usd=self.hard_limit_usd,
        )

    def check_before_call(self) -> None:
        """Refuse a new model call once the hard limit is already reached.

        Called *before* spending so the budget fails closed: a session that has
        hit the cap will not make one more (billable) call.

        Raises:
            BudgetExceeded: when cumulative cost is at/above ``hard_limit_usd``.
        """
        if self.cost_usd >= self.hard_limit_usd:
            raise BudgetExceeded(
                f"Session budget exhausted: {_usd(self.cost_usd)} spent reaches the "
                f"{_usd(self.hard_limit_usd)} hard limit. No further model calls will be "
                "made this session. Start a new session or raise the limit if this is expected."
            )

    def record(self, usage: TokenUsage | None) -> str | None:
        """Add one call's usage to the running total; return a soft-limit warning.

        Args:
            usage: the call's token usage (``None`` when the provider omitted
                it — nothing is added, honestly).

        Returns:
            A one-line warning string the first time cumulative cost crosses the
            soft limit (and while it stays over), otherwise ``None``.
        """
        if usage is not None:
            self.input_tokens += usage.input_tokens
            self.output_tokens += usage.output_tokens
            self.cost_usd = estimate_cost_usd(
                TokenUsage(input_tokens=self.input_tokens, output_tokens=self.output_tokens),
                self.input_per_mtok,
                self.output_per_mtok,
            )
        if self.cost_usd >= self.soft_limit_usd:
            self._soft_warned = True
            return (
                f"Budget warning: {_usd(self.cost_usd)} spent has reached the "
                f"{_usd(self.soft_limit_usd)} soft limit (hard limit "
                f"{_usd(self.hard_limit_usd)}). Consider wrapping up this session."
            )
        return None


def guarded_complete(
    llm: LLMClient,
    messages: list[ChatMessage],
    budget: SessionBudget,
    *,
    max_output_tokens: int,
    timeout_s: float = 30.0,
    temperature: float = 0.0,
) -> tuple[ChatResult, str | None]:
    """Make a budget-, token-, and timeout-guarded model call.

    Enforcement order (each guards a distinct failure):

    1. ``budget.check_before_call()`` — fail closed if the hard limit is
       already reached (no billable call is made).
    2. ``max_output_tokens`` cap — bound the expensive (output) side. Pass
       ``settings.max_output_tokens`` so this matches the deployment default.
    3. ``timeout_s`` wall clock — a hung provider raises
       :class:`ModelCallTimeout` instead of stalling the whole session.
    4. ``budget.record(...)`` — bill the call and surface a soft-limit warning.

    Args:
        llm: any :class:`~techcorp_agent.llm.base.LLMClient`.
        messages: the conversation to send.
        budget: the session budget to enforce and update.
        max_output_tokens: hard cap on generated tokens.
        timeout_s: wall-clock timeout for the provider call.
        temperature: sampling temperature (default 0 for testable output).

    Returns:
        ``(result, warning)`` — the ``ChatResult`` and a soft-limit warning
        string (or ``None``).

    Raises:
        BudgetExceeded: the hard limit was already reached before this call.
        ModelCallTimeout: the provider did not respond within ``timeout_s``.
    """
    budget.check_before_call()

    # A thread-based watchdog gives a portable, offline-safe timeout that works
    # for any synchronous LLMClient (real or mock) without touching signals.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            llm.complete,
            messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
        )
        try:
            result = future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError as exc:
            raise ModelCallTimeout(
                f"Model call exceeded the {timeout_s:.0f}s timeout and was abandoned. "
                "The provider may be slow or unreachable; try again or check connectivity."
            ) from exc

    warning = budget.record(result.usage)
    return result, warning
