"""Module 02 solution — TechCorp's first scripted assistant call.

Runs fully offline: with no OPENAI_API_KEY configured, get_llm_client()
returns the deterministic mock client, so this script always produces output.

Run it:
    uv run python course/02_first_api_call/solution/first_call.py
"""

import sys

from techcorp_agent.config import Settings, get_settings
from techcorp_agent.costs import estimate_cost_usd
from techcorp_agent.llm.base import LLMClient, ProviderError
from techcorp_agent.llm.factory import get_llm_client
from techcorp_agent.schemas import ChatMessage, ChatResult

SYSTEM_PROMPT = "You are TechCorp's internal assistant."
DEFAULT_QUESTION = "In one sentence, what should I do when a customer asks for a refund?"


def build_messages(question: str) -> list[ChatMessage]:
    """Task 3: a system message that sets behavior, then the user's question."""
    return [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=question),
    ]


def run_request(client: LLMClient, messages: list[ChatMessage]) -> ChatResult:
    """Tasks 2-3: send the conversation through the client adapter.

    temperature=0.0 keeps the answer as deterministic as the provider allows,
    which is the right default for a scripted internal tool.
    """
    return client.complete(messages, temperature=0.0)


def inspect_result(result: ChatResult) -> None:
    """Task 5: the response is a rich object, not a plain string — walk it safely."""
    print("\n--- Full response (safely inspected) ---")
    print(f"model:   {result.model}")
    print(f"content: {result.content!r}")
    if result.raw is None:
        print("raw:     (no raw provider payload — offline mock client)")
    else:
        # Never index blindly: choices can be empty, content can be None.
        choices = getattr(result.raw, "choices", None) or []
        finish_reason = choices[0].finish_reason if choices else "(no choices returned)"
        print(f"raw:     id={getattr(result.raw, 'id', '?')} finish_reason={finish_reason}")


def summarize_usage(result: ChatResult, settings: Settings) -> float | None:
    """Tasks 6-7: report token usage and estimated cost.

    Returns the estimated cost in USD, or None when the provider reported no
    usage (usage is optional in the API contract — never assume it exists).
    """
    print("\n--- Usage & estimated cost ---")
    if result.usage is None:
        print("usage:   not reported by the provider — cost unknown")
        return None

    usage = result.usage
    print(f"input tokens:  {usage.input_tokens}")
    print(f"output tokens: {usage.output_tokens}")
    print(f"total tokens:  {usage.total_tokens}")
    cost = estimate_cost_usd(usage, settings.cost_input_per_mtok, settings.cost_output_per_mtok)
    print(
        f"estimated cost: ${cost:.6f} "
        f"(${settings.cost_input_per_mtok:.2f}/M input, "
        f"${settings.cost_output_per_mtok:.2f}/M output)"
    )
    return cost


def main() -> int:
    settings = get_settings()  # Task 1: configuration from environment / .env
    client = get_llm_client(settings)  # Task 2: mock offline, real client with a key
    print(f"client: {client.name}")

    messages = build_messages(DEFAULT_QUESTION)
    try:
        result = run_request(client, messages)
    except ProviderError as exc:  # Task 8: auth/network/status errors, made actionable
        print(f"\nProvider call failed: {exc}", file=sys.stderr)
        print("Fix the setting the message names in .env, then re-run.", file=sys.stderr)
        return 1

    print("\n--- Assistant ---")  # Task 4
    print(result.content)

    inspect_result(result)  # Task 5
    summarize_usage(result, settings)  # Tasks 6-7
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
