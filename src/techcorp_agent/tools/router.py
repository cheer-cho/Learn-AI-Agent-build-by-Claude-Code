"""Route a question to the right tool — or to none — and run it safely.

Two routers, used together:

- ``route_question`` asks the LLM to pick a tool via a constrained prompt whose
  only valid answers are the tool names or ``"none"``. The model is good at
  reading intent ("where is my order" -> order_lookup) but can drift: it may
  reply with prose, a made-up tool name, or the wrong tool.
- ``keyword_route`` is a deterministic fallback that decides from surface
  patterns (an order id, a math expression, policy words). It never calls a
  model, so it is cheap, testable, and always available. ``route_question``
  falls back to it whenever the LLM's reply is not a valid tool name.

``run_tool`` executes a selected tool with argument validation and an optional
timeout, always returning a ``ToolResult`` — the agent loop never sees a raw
exception from a tool.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any

from techcorp_agent.llm.base import LLMClient
from techcorp_agent.schemas import ChatMessage
from techcorp_agent.tools.base import ToolResult, ToolSpec

NO_TOOL = "none"

_ORDER_ID_RE = re.compile(r"\bTC-\d{3,}\b", re.IGNORECASE)
# A math-ish expression: at least two numbers joined by an operator, or a percent.
_MATH_RE = re.compile(r"\d[\d\s.,]*\s*[-+*/%^]\s*\d|\d+(?:\.\d+)?\s*%")
_MATH_WORDS = ("calculate", "how much is", "what is ", "multiplied by", "times", "plus", "minus")
_POLICY_WORDS = (
    "policy",
    "warranty",
    "refund",
    "return",
    "returns",
    "privacy",
    "vacation",
    "remote",
    "restocking",
    "deletion",
    "escalation",
    "stipend",
    "sick leave",
    "dress code",
    "coverage",
)


def _router_prompt(question: str, tools: list[ToolSpec]) -> list[ChatMessage]:
    catalog = "\n".join(f"- {tool.name}: {tool.description}" for tool in tools)
    system = (
        "You are a router. Choose exactly one tool to answer the user's question, "
        "or 'none' if no tool fits (greetings, general explanations answerable "
        "without company data or math).\n\n"
        f"Available tools:\n{catalog}\n\n"
        "Reply with ONLY the tool name or the word 'none'. No punctuation, no "
        "explanation."
    )
    return [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=question),
    ]


def keyword_route(question: str, tools: list[ToolSpec] | None = None) -> str:
    """Deterministically pick a tool name from surface patterns, or ``NO_TOOL``.

    Order matters: an explicit order id or a math expression is a strong signal
    and is checked before the weaker policy-keyword heuristic. Returns a tool
    name only if a tool with that name is available (when ``tools`` is given).
    """
    available = {tool.name for tool in tools} if tools is not None else None

    def pick(name: str) -> str:
        if available is None or name in available:
            return name
        return NO_TOOL

    text = question.lower()

    if _ORDER_ID_RE.search(question):
        return pick("order_lookup")
    has_math_expr = bool(_MATH_RE.search(question))
    has_math_word = any(w in text for w in _MATH_WORDS)
    if has_math_expr or (has_math_word and re.search(r"\d", text)):
        return pick("calculator")
    if any(word in text for word in _POLICY_WORDS):
        return pick("document_search")
    return NO_TOOL


def route_question(question: str, llm: LLMClient, tools: list[ToolSpec]) -> str:
    """Ask the LLM to choose a tool; fall back to ``keyword_route`` on a bad reply.

    The defense against wrong/invalid tool selection is the fallback: if the
    model returns anything that is not a known tool name or ``'none'`` (prose, a
    hallucinated tool, empty), we ignore it and route deterministically.
    """
    valid = {tool.name for tool in tools} | {NO_TOOL}
    result = llm.complete(_router_prompt(question, tools), temperature=0.0)
    reply = result.content.strip().strip(".").lower()
    # Normalize: the model sometimes wraps the answer ("tool: calculator").
    for name in valid:
        if reply == name:
            return name
    # Reply was not a clean tool name — deterministic fallback.
    return keyword_route(question, tools)


def run_tool(
    tool: ToolSpec,
    raw_args: dict[str, Any],
    timeout_seconds: float | None = None,
) -> ToolResult:
    """Run ``tool`` with validated ``raw_args``, converting every failure mode
    into a ``ToolResult``.

    Handles four failure modes uniformly:
    - missing/invalid argument -> validation failure (via ``ToolSpec.run``);
    - the tool raising          -> caught here, returned as a failure;
    - the tool timing out       -> a timeout failure (when ``timeout_seconds`` set);
    - the tool returning no data -> already a ``ToolResult`` failure from the tool.
    """

    def _invoke() -> ToolResult:
        try:
            return tool.run(raw_args)
        except Exception as exc:  # noqa: BLE001 — a tool crash must not crash the agent
            return ToolResult.failure(tool.name, f"Tool '{tool.name}' raised: {exc}")

    if timeout_seconds is None:
        return _invoke()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_invoke)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeout:
            return ToolResult.failure(
                tool.name,
                f"Tool '{tool.name}' timed out after {timeout_seconds:g}s.",
            )
