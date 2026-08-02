"""Choose the right LLM client for the current configuration."""

from techcorp_agent.config import Settings, get_settings
from techcorp_agent.llm.base import LLMClient


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    """Mock client when offline (no key or TECHCORP_OFFLINE=true), real client otherwise."""
    settings = settings or get_settings()
    if settings.offline:
        from techcorp_agent.llm.mock_client import MockLLMClient

        return MockLLMClient()
    from techcorp_agent.llm.openai_client import OpenAIChatClient

    return OpenAIChatClient(settings)
