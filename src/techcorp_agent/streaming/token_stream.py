"""Token-level streaming for TechCorp's agent.

The application ``LLMClient`` protocol (``techcorp_agent.llm.base``) only exposes
``complete()`` — it returns the *whole* reply at once. That is the right shape
for scripted internal tools, but it makes a CLI feel frozen: the user stares at a
blank line for two seconds, then the full answer appears at once.

This module adds a **separate, additive** capability — ``StreamingLLM`` — that
yields the reply in chunks as it is produced. It deliberately does *not* modify
the shared ``LLMClient`` protocol (that package is owned elsewhere); token
streaming is a Module 16 concern layered on top.

Two implementations, mirroring the rest of the course:

- :class:`MockStreamingLLM` — deterministic, offline, yields a scripted reply
  word by word so labs and tests are exact and need no network.
- :class:`OpenAIStreamingClient` — the live path, wrapping the raw OpenAI SDK's
  ``chat.completions.create(stream=True)`` with the same actionable error
  guarding as ``techcorp_agent.llm.openai_client`` (lazy import, no key = no
  import).

Both satisfy the :class:`StreamingLLM` protocol: ``stream_complete(messages)``
returns an ``Iterator[str]`` of text chunks. :func:`collect` reassembles chunks
into the full string — the exact text you would have gotten from a single
non-streaming call.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Protocol, runtime_checkable

from techcorp_agent.schemas import ChatMessage


@runtime_checkable
class StreamingLLM(Protocol):
    """A client that can stream a reply as a sequence of text chunks.

    A chunk is a piece of the assistant's text (a word, a token, a few
    characters) — never a control object. Concatenating every chunk yields the
    complete reply, so ``collect(client.stream_complete(msgs))`` is equivalent
    to a single non-streaming completion's content.
    """

    name: str

    def stream_complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Yield the assistant reply chunk by chunk, in order."""
        ...


def collect(chunks: Iterable[str]) -> str:
    """Reassemble streamed chunks into the full reply text.

    This is the bridge back to the non-streaming world: a caller that only wants
    the final answer (a test, a logger, a later batch step) drains the stream
    and joins it. Streaming is a *delivery* choice, not a different answer.
    """
    return "".join(chunks)


def _iter_word_chunks(text: str) -> Iterator[str]:
    """Split ``text`` into chunks that reassemble to exactly ``text``.

    We keep each whitespace run attached to the word before it, so joining the
    chunks with ``""`` reproduces the original string byte for byte (spaces and
    newlines included). This is what makes the mock deterministic *and* faithful:
    ``collect(...) == text`` always holds.
    """
    if not text:
        return
    chunk = ""
    for char in text:
        chunk += char
        if char.isspace():
            yield chunk
            chunk = ""
    if chunk:
        yield chunk


class MockStreamingLLM:
    """Deterministic offline streaming client.

    Scripted mode: ``MockStreamingLLM(responses=[...])`` streams those replies in
    order, one per ``stream_complete`` call, each broken into word-sized chunks.
    Echo mode (no script): it streams a deterministic reply derived from the last
    user message, so labs stay runnable offline.

    Like ``MockLLMClient`` it records every call in ``.calls`` so tests can assert
    on the exact prompts the application sent.
    """

    name = "mock-streaming-offline"

    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses) if responses else []
        self.calls: list[list[ChatMessage]] = []

    def stream_complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        if not messages:
            raise ValueError("messages must not be empty")
        self.calls.append(list(messages))

        if self._responses:
            text = self._responses.pop(0)
        else:
            last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
            text = (
                "[offline mock] Streaming your message back: "
                f"{last_user[:200]}. Configure OPENAI_API_KEY for live streaming."
            )

        if max_tokens is not None:
            text = text[: max_tokens * 4]

        yield from _iter_word_chunks(text)


class OpenAIStreamingClient:
    """Live token streaming over the raw OpenAI-compatible SDK.

    Wraps ``client.chat.completions.create(stream=True)``, which yields
    ``ChatCompletionChunk`` objects; the text lives at
    ``chunk.choices[0].delta.content`` and is ``None`` on the role/finish chunks,
    which we skip. Errors are translated to :class:`ProviderError` with the same
    actionable messages as the non-streaming client, so a missing key or a
    downed endpoint is a clear instruction, not a traceback.

    The ``openai`` import is lazy (constructor only), so offline users never need
    a working provider install just to import this module.
    """

    def __init__(self, settings=None):
        from techcorp_agent.config import get_settings
        from techcorp_agent.llm.base import ProviderError

        settings = settings or get_settings()
        if not settings.openai_api_key:
            raise ProviderError(
                "No API key configured. Set OPENAI_API_KEY in .env, "
                "or run offline with MockStreamingLLM."
            )
        from openai import OpenAI

        self._client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        self._model = settings.openai_model
        self._default_max_tokens = settings.max_output_tokens
        self.name = f"openai-streaming:{self._model}"

    def stream_complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        from openai import APIConnectionError, APIStatusError, AuthenticationError

        from techcorp_agent.llm.base import ProviderError

        if not messages:
            raise ValueError("messages must not be empty")
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=[m.model_dump() for m in messages],
                temperature=temperature,
                max_tokens=max_tokens or self._default_max_tokens,
                stream=True,
            )
            for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                text = getattr(delta, "content", None) if delta else None
                if text:
                    yield text
        except AuthenticationError as exc:
            raise ProviderError(
                "Authentication failed (401). Check OPENAI_API_KEY in .env — "
                "it may be missing, expired, or for a different OPENAI_BASE_URL."
            ) from exc
        except APIConnectionError as exc:
            raise ProviderError(
                f"Could not reach the provider at {self._client.base_url}. "
                "Check your network and OPENAI_BASE_URL."
            ) from exc
        except APIStatusError as exc:
            raise ProviderError(
                f"Provider returned HTTP {exc.status_code}: {exc.message}. "
                f"Check OPENAI_MODEL ('{self._model}') is available on this endpoint."
            ) from exc
