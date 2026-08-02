"""Module 02 starter — TechCorp's first scripted assistant call.

Work through lab.md and replace each TODO. The script is runnable at every
stage: unimplemented steps stop with a pointer to the task instead of a crash.

Run it:
    uv run python course/02_first_api_call/starter/first_call.py
Check it:
    uv run pytest course/02_first_api_call -q
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
    """Task 3: build the conversation to send."""
    # TODO: Return a list of ChatMessage objects: first a "system" message
    #       containing SYSTEM_PROMPT, then a "user" message containing `question`.
    raise NotImplementedError("build_messages — see lab.md Task 3")


def run_request(client: LLMClient, messages: list[ChatMessage]) -> ChatResult:
    """Tasks 2-3: send the conversation and return the normalized result."""
    # TODO: Call client.complete(...) with the messages and temperature=0.0,
    #       and return the ChatResult it gives back.
    raise NotImplementedError("run_request — see lab.md Task 3")


def inspect_result(result: ChatResult) -> None:
    """Task 5: the response is a rich object, not a plain string — walk it safely."""
    print("\n--- Full response (safely inspected) ---")
    # TODO: Print result.model and result.content (use !r so empty strings are visible).
    # TODO: If result.raw is None, say the raw payload is unavailable (offline mock).
    #       Otherwise print the first choice's finish_reason — WITHOUT assuming
    #       result.raw.choices is non-empty.
    raise NotImplementedError("inspect_result — see lab.md Task 5")


def summarize_usage(result: ChatResult, settings: Settings) -> float | None:
    """Tasks 6-7: report token usage and estimated cost.

    Must return the estimated USD cost, or None when usage was not reported.
    """
    print("\n--- Usage & estimated cost ---")
    # TODO: If result.usage is None, print that usage was not reported and return None.
    # TODO: Otherwise print input_tokens, output_tokens, and total_tokens, then
    #       compute the cost with estimate_cost_usd(usage,
    #       settings.cost_input_per_mtok, settings.cost_output_per_mtok),
    #       print it, and return it.
    raise NotImplementedError("summarize_usage — see lab.md Tasks 6-7")


def main() -> int:
    settings = get_settings()  # Task 1: configuration from environment / .env
    client = get_llm_client(settings)  # Task 2: mock offline, real client with a key
    print(f"client: {client.name}")

    messages = build_messages(DEFAULT_QUESTION)

    # TODO: Task 8 — wrap the run_request call in try/except ProviderError.
    #       On error: print the message (it already says which .env setting to fix)
    #       to sys.stderr and return 1.
    result = run_request(client, messages)

    print("\n--- Assistant ---")  # Task 4
    print(result.content)

    inspect_result(result)  # Task 5
    summarize_usage(result, settings)  # Tasks 6-7
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NotImplementedError as exc:
        print(f"\nNot implemented yet: {exc}")
        print("Open course/02_first_api_call/lab.md and work through the tasks in order.")
        raise SystemExit(1) from None
