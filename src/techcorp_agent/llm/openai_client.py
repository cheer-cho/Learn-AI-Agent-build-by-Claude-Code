"""OpenAI-compatible chat client (works with OpenAI, OpenRouter, Ollama, and
any provider exposing the /chat/completions API)."""

from techcorp_agent.config import Settings, get_settings
from techcorp_agent.llm.base import ProviderError
from techcorp_agent.schemas import ChatMessage, ChatResult, TokenUsage


class OpenAIChatClient:
    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        if not settings.openai_api_key:
            raise ProviderError(
                "No API key configured. Set OPENAI_API_KEY in .env, "
                "or run in offline mode (leave it blank and use the mock client)."
            )
        # Imported lazily so offline users never need working provider setup.
        from openai import OpenAI

        self._client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        self._model = settings.openai_model
        self._default_max_tokens = settings.max_output_tokens
        self.name = f"openai-compatible:{self._model}"

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResult:
        from openai import APIConnectionError, APIStatusError, AuthenticationError

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[m.model_dump() for m in messages],
                temperature=temperature,
                max_tokens=max_tokens or self._default_max_tokens,
            )
        except AuthenticationError as exc:
            raise ProviderError(
                "Authentication failed (401). Check OPENAI_API_KEY in .env — "
                "it may be missing, expired, or for a different OPENAI_BASE_URL."
            ) from exc
        except APIConnectionError as exc:
            raise ProviderError(
                f"Could not reach the provider at "
                f"{self._client.base_url}. Check your network and OPENAI_BASE_URL."
            ) from exc
        except APIStatusError as exc:
            raise ProviderError(
                f"Provider returned HTTP {exc.status_code}: {exc.message}. "
                f"Check OPENAI_MODEL ('{self._model}') is available on this endpoint."
            ) from exc

        choice = response.choices[0] if response.choices else None
        content = (choice.message.content or "") if choice else ""

        # Usage is optional in the API contract — never assume it is present.
        usage = None
        if response.usage is not None:
            usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
            )

        return ChatResult(content=content, model=response.model, usage=usage, raw=response)
