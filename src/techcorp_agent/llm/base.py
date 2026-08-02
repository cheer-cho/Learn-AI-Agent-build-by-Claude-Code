"""The application-facing LLM interface.

This is the "small adapter" the course keeps provider-specific code behind:

- raw provider SDK        → openai_client.OpenAIChatClient (wraps `openai`)
- offline deterministic   → mock_client.MockLLMClient
- framework abstraction   → LangChain, introduced separately in Module 03

Application code depends only on this protocol, never on a vendor SDK.
"""

from typing import Protocol, runtime_checkable

from techcorp_agent.schemas import ChatMessage, ChatResult


class ProviderError(RuntimeError):
    """A provider call failed. The message must tell the learner what to do next."""


@runtime_checkable
class LLMClient(Protocol):
    name: str

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """Send a conversation and return the assistant's reply."""
        ...
