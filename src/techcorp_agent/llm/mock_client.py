"""Deterministic offline LLM used when no API key is configured.

Two modes:

- scripted:  MockLLMClient(responses=[...]) returns those responses in order —
  this is what tests use to make behavior fully predictable.
- echo:      with no script, it produces a deterministic reply derived from the
  last user message, so labs remain runnable (if less interesting) offline.

It also records every call in `.calls`, which lets tests assert on the exact
prompts the application sent.
"""

from techcorp_agent.schemas import ChatMessage, ChatResult, TokenUsage


def _approx_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token) — good enough for offline labs."""
    return max(1, len(text) // 4)


class MockLLMClient:
    name = "mock-offline"

    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses) if responses else []
        self.calls: list[list[ChatMessage]] = []

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResult:
        if not messages:
            raise ValueError("messages must not be empty")
        self.calls.append(list(messages))

        if self._responses:
            content = self._responses.pop(0)
        else:
            last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
            content = (
                "[offline mock] I received your message: "
                f"{last_user[:200]!r}. Configure OPENAI_API_KEY in .env for real answers."
            )

        if max_tokens is not None:
            content = content[: max_tokens * 4]

        input_text = " ".join(m.content for m in messages)
        usage = TokenUsage(
            input_tokens=_approx_tokens(input_text),
            output_tokens=_approx_tokens(content),
        )
        return ChatResult(content=content, model=self.name, usage=usage)
